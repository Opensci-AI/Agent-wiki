"""Multi-provider LLM streaming client with fallback support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------

@dataclass
class LLMProvider:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    build_body: Callable[[list[dict], str], dict] = lambda msgs, model: {}
    parse_line: Callable[[str], str | None] = lambda line: None


# ---------------------------------------------------------------------------
# Body builders
# ---------------------------------------------------------------------------

def _build_openai_body(messages: list[dict], model: str) -> dict:
    return {"model": model, "messages": messages, "stream": True}


def _build_anthropic_body(messages: list[dict], model: str) -> dict:
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    body: dict = {
        "model": model,
        "messages": non_system,
        "max_tokens": 4096,
        "stream": True,
    }
    if system_msgs:
        body["system"] = system_msgs[0]["content"]
    return body


def _build_google_body(messages: list[dict], model: str) -> dict:
    """Build request body for Google Gemini API.

    Supports multimodal content when message contains 'images' key.
    """
    contents = []
    system_instruction = None
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
            continue
        role = "model" if m["role"] == "assistant" else "user"

        # Build parts array
        parts = []
        if m.get("content"):
            parts.append({"text": m["content"]})

        for img in m.get("images", []):
            parts.append({
                "inline_data": {
                    "mime_type": img["mime_type"],
                    "data": img["data"]
                }
            })

        if parts:
            contents.append({"role": role, "parts": parts})

    body: dict = {"contents": contents}
    if system_instruction:
        body["system_instruction"] = {"parts": [{"text": system_instruction}]}
    return body


def _build_vertex_body(messages: list[dict], model: str) -> dict:
    """Build request body for Vertex AI Gemini API.

    Supports multimodal content when message contains 'images' key:
    {"role": "user", "content": "text", "images": [{"mime_type": "image/png", "data": "base64..."}]}
    """
    contents = []
    system_instruction = None
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
            continue
        role = "model" if m["role"] == "assistant" else "user"

        # Build parts array - text first, then images
        parts = []
        if m.get("content"):
            parts.append({"text": m["content"]})

        # Add image parts if present
        for img in m.get("images", []):
            parts.append({
                "inlineData": {
                    "mimeType": img["mime_type"],
                    "data": img["data"]
                }
            })

        if parts:
            contents.append({"role": role, "parts": parts})

    body: dict = {"contents": contents}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    return body


# ---------------------------------------------------------------------------
# Line parsers
# ---------------------------------------------------------------------------

def _parse_openai_line(line: str) -> str | None:
    """Parse SSE lines from OpenAI-compatible APIs."""
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
        return data["choices"][0]["delta"].get("content")
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def _parse_anthropic_line(line: str) -> str | None:
    """Parse SSE lines from the Anthropic Messages API."""
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    try:
        data = json.loads(payload)
        if data.get("type") == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text")
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _parse_google_line(line: str) -> str | None:
    """Parse SSE lines from the Google Gemini API."""
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    try:
        data = json.loads(payload)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def _parse_vertex_line(line: str) -> str | None:
    """Parse SSE lines from the Vertex AI Gemini API."""
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    try:
        data = json.loads(payload)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Vertex AI Authentication (with auto-refresh)
# ---------------------------------------------------------------------------

_vertex_credentials = None


def _get_vertex_access_token() -> str | None:
    """Get access token from Google Application Default Credentials (ADC).

    Uses cached credentials and auto-refreshes when expired.
    Production-ready: no manual re-auth needed.
    """
    global _vertex_credentials

    try:
        import google.auth
        import google.auth.transport.requests

        # Initialize credentials once, reuse afterwards
        if _vertex_credentials is None:
            _vertex_credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

        # Auto-refresh if expired (happens automatically)
        if not _vertex_credentials.valid:
            _vertex_credentials.refresh(google.auth.transport.requests.Request())

        return _vertex_credentials.token
    except Exception as e:
        logger.warning(f"Failed to get Vertex AI access token: {e}")
        return None


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def get_provider(config: dict) -> LLMProvider:
    """Return a configured LLMProvider from a config dict.

    Expected keys: provider, apiKey, model, and optionally baseUrl.
    """
    provider = config.get("provider", "openai")
    api_key = config.get("apiKey", "")
    model = config.get("model", "")
    base_url = config.get("baseUrl", "")

    if provider == "openrouter":
        return LLMProvider(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            build_body=_build_openai_body,
            parse_line=_parse_openai_line,
        )

    if provider == "openai":
        return LLMProvider(
            url="https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            build_body=_build_openai_body,
            parse_line=_parse_openai_line,
        )

    if provider == "anthropic":
        return LLMProvider(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            build_body=_build_anthropic_body,
            parse_line=_parse_anthropic_line,
        )

    if provider == "google":
        return LLMProvider(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}",
            headers={},
            build_body=_build_google_body,
            parse_line=_parse_google_line,
        )

    if provider == "vertex":
        # Vertex AI Gemini - uses ADC for authentication
        project_id = config.get("projectId", "")
        location = config.get("location", "global")
        access_token = _get_vertex_access_token()

        if location == "global":
            # Global endpoint
            url = f"https://aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/global/publishers/google/models/{model}:streamGenerateContent?alt=sse"
        else:
            # Regional endpoint
            url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:streamGenerateContent?alt=sse"

        return LLMProvider(
            url=url,
            headers={"Authorization": f"Bearer {access_token}"} if access_token else {},
            build_body=_build_vertex_body,
            parse_line=_parse_vertex_line,
        )

    if provider == "ollama":
        host = base_url or "http://localhost:11434"
        return LLMProvider(
            url=f"{host}/v1/chat/completions",
            headers={},
            build_body=_build_openai_body,
            parse_line=_parse_openai_line,
        )

    # custom — user supplies baseUrl
    return LLMProvider(
        url=f"{base_url}/v1/chat/completions" if base_url else "http://localhost:8000/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        build_body=_build_openai_body,
        parse_line=_parse_openai_line,
    )


# ---------------------------------------------------------------------------
# Streaming & non-streaming helpers
# ---------------------------------------------------------------------------

async def _stream_with_provider(config: dict, messages: list[dict]) -> AsyncGenerator[str, None]:
    """Internal: Stream tokens from a single provider (no fallback)."""
    provider = get_provider(config)
    model = config.get("model", "")
    body = provider.build_body(messages, model)

    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0)) as client:
        async with client.stream(
            "POST",
            provider.url,
            headers={"Content-Type": "application/json", **provider.headers},
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                token = provider.parse_line(line)
                if token:
                    yield token


async def stream_chat(config: dict, messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream tokens from the configured LLM provider with fallback support.

    If config contains a 'fallback' key with another config dict,
    it will be tried if the primary provider fails.
    """
    fallback_config = config.get("fallback")

    try:
        async for token in _stream_with_provider(config, messages):
            yield token
    except Exception as primary_error:
        if fallback_config:
            logger.warning(
                f"Primary LLM provider failed: {primary_error}. Trying fallback..."
            )
            try:
                async for token in _stream_with_provider(fallback_config, messages):
                    yield token
                return
            except Exception as fallback_error:
                logger.error(f"Fallback LLM provider also failed: {fallback_error}")
                raise primary_error
        else:
            raise


async def complete_chat(config: dict, messages: list[dict]) -> str:
    """Non-streaming chat: collects the full response as a single string.

    Supports fallback if config contains a 'fallback' key.
    """
    fallback_config = config.get("fallback")

    try:
        tokens: list[str] = []
        async for token in _stream_with_provider(config, messages):
            tokens.append(token)
        return "".join(tokens)
    except Exception as primary_error:
        if fallback_config:
            logger.warning(
                f"Primary LLM provider failed: {primary_error}. Trying fallback..."
            )
            try:
                tokens = []
                async for token in _stream_with_provider(fallback_config, messages):
                    tokens.append(token)
                return "".join(tokens)
            except Exception as fallback_error:
                logger.error(f"Fallback LLM provider also failed: {fallback_error}")
                raise primary_error
        else:
            raise


async def extract_text_from_image(
    config: dict,
    image_data: bytes,
    mime_type: str,
    prompt: str = "Extract all text from this image. Return only the extracted text, no explanations."
) -> str:
    """Extract text from an image using multimodal LLM.

    Args:
        config: LLM configuration dict
        image_data: Raw image bytes
        mime_type: Image MIME type (e.g., 'image/png', 'image/jpeg')
        prompt: Extraction prompt

    Returns:
        Extracted text from the image
    """
    import base64

    b64_data = base64.b64encode(image_data).decode("utf-8")

    messages = [
        {
            "role": "user",
            "content": prompt,
            "images": [{"mime_type": mime_type, "data": b64_data}]
        }
    ]

    return await complete_chat(config, messages)
