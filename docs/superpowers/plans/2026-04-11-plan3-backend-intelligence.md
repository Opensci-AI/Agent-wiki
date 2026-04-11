# Plan 3: Backend Intelligence — LLM, Chat, Ingest, Research, SSE

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM streaming proxy, chat conversations, 2-step ingest pipeline, deep research with web search, and SSE real-time streaming — the "intelligence" layer of the wiki.

**Architecture:** LLM calls go through backend (protects API keys). Multi-provider support (OpenRouter, OpenAI, Anthropic, Google, Ollama, custom). Ingest and research run as background tasks with SSE progress streaming. Chat supports multi-turn conversations with streaming responses.

**Tech Stack:** httpx (LLM streaming), sse-starlette (SSE), existing FastAPI + SQLAlchemy stack

**Spec:** `docs/superpowers/specs/2026-04-10-llm-wiki-web-design.md`

**Depends on:** Plan 1 (auth, projects, config) + Plan 2 (pages, sources, storage, extraction, background tasks)

**Port from TypeScript:** `src/lib/llm-client.ts`, `src/lib/llm-providers.ts`, `src/lib/ingest.ts`, `src/lib/deep-research.ts`, `src/lib/web-search.ts`, `src/stores/chat-store.ts`

---

## File Structure

```
backend/app/
├── models/
│   ├── conversation.py            # Conversation ORM
│   ├── message.py                 # Message ORM
│   └── ingest_cache.py            # IngestCache ORM
│
├── schemas/
│   └── chat.py                    # Chat request/response schemas
│
├── services/
│   ├── chat_service.py            # Conversation CRUD + LLM chat
│   ├── ingest_service.py          # 2-step ingest pipeline
│   └── research_service.py        # Deep research pipeline
│
├── core/
│   ├── llm_client.py              # Multi-provider LLM streaming
│   ├── web_search.py              # Tavily integration
│   └── sse.py                     # SSE helper
│
├── api/
│   ├── chat.py                    # /conversations/* routes
│   ├── ingest.py                  # /projects/:id/ingest/* routes
│   ├── research.py                # /projects/:id/research/* routes
│   └── streams.py                 # SSE stream endpoints

backend/tests/
├── test_llm_client.py
├── test_chat.py
├── test_ingest.py
└── test_web_search.py
```

---

### Task 1: Core Modules — LLM Client + Web Search + SSE

**Files:**
- Create: `backend/app/core/llm_client.py`
- Create: `backend/app/core/web_search.py`
- Create: `backend/app/core/sse.py`
- Create: `backend/tests/test_llm_client.py`
- Create: `backend/tests/test_web_search.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add dependencies**

Append to `backend/requirements.txt`:
```
sse-starlette==2.1.0
```
Install: `pip install sse-starlette==2.1.0`

- [ ] **Step 2: Create LLM client**

```python
# backend/app/core/llm_client.py
import json
import httpx
from typing import AsyncGenerator
from app.config import settings

class LLMProvider:
    """Configuration for an LLM provider endpoint."""
    def __init__(self, url: str, headers: dict, build_body: callable, parse_line: callable):
        self.url = url
        self.headers = headers
        self.build_body = build_body
        self.parse_line = parse_line

def _parse_openai_line(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    if data == "[DONE]":
        return None
    try:
        parsed = json.loads(data)
        return parsed.get("choices", [{}])[0].get("delta", {}).get("content")
    except (json.JSONDecodeError, IndexError):
        return None

def _parse_anthropic_line(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    try:
        parsed = json.loads(data)
        if parsed.get("type") == "content_block_delta" and parsed.get("delta", {}).get("type") == "text_delta":
            return parsed["delta"].get("text")
    except json.JSONDecodeError:
        pass
    return None

def _parse_google_line(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    try:
        parsed = json.loads(data)
        return parsed.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
    except (json.JSONDecodeError, IndexError):
        return None

def _build_openai_body(messages: list[dict], model: str) -> dict:
    return {"messages": messages, "model": model, "stream": True}

def _build_anthropic_body(messages: list[dict], model: str) -> dict:
    system_msgs = [m for m in messages if m["role"] == "system"]
    conv_msgs = [m for m in messages if m["role"] != "system"]
    body = {"messages": conv_msgs, "model": model, "stream": True, "max_tokens": 4096}
    if system_msgs:
        body["system"] = "\n".join(m["content"] for m in system_msgs)
    return body

def _build_google_body(messages: list[dict], model: str) -> dict:
    system_msgs = [m for m in messages if m["role"] == "system"]
    conv_msgs = [m for m in messages if m["role"] != "system"]
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in conv_msgs]
    body = {"contents": contents}
    if system_msgs:
        body["systemInstruction"] = {"parts": [{"text": m["content"]} for m in system_msgs]}
    return body

def get_provider(config: dict) -> LLMProvider:
    """Get LLM provider from config dict. Config keys: provider, apiKey, model, ollamaUrl, customEndpoint."""
    provider = config.get("provider", "openrouter")
    api_key = config.get("apiKey", "")
    model = config.get("model", "")
    ollama_url = config.get("ollamaUrl", "http://localhost:11434")
    custom_endpoint = config.get("customEndpoint", "")

    if provider == "openai":
        return LLMProvider(
            url="https://api.openai.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            build_body=lambda msgs: _build_openai_body(msgs, model),
            parse_line=_parse_openai_line,
        )
    elif provider == "anthropic":
        return LLMProvider(
            url="https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
            build_body=lambda msgs: _build_anthropic_body(msgs, model),
            parse_line=_parse_anthropic_line,
        )
    elif provider == "google":
        return LLMProvider(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            build_body=lambda msgs: _build_google_body(msgs, model),
            parse_line=_parse_google_line,
        )
    elif provider == "ollama":
        return LLMProvider(
            url=f"{ollama_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            build_body=lambda msgs: _build_openai_body(msgs, model),
            parse_line=_parse_openai_line,
        )
    elif provider == "custom":
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return LLMProvider(
            url=f"{custom_endpoint}/chat/completions",
            headers=headers,
            build_body=lambda msgs: _build_openai_body(msgs, model),
            parse_line=_parse_openai_line,
        )
    else:  # openrouter (default)
        return LLMProvider(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}",
                     "HTTP-Referer": "https://agent-wiki.local", "X-Title": "Agent Wiki"},
            build_body=lambda msgs: _build_openai_body(msgs, model),
            parse_line=_parse_openai_line,
        )

async def stream_chat(config: dict, messages: list[dict]) -> AsyncGenerator[str, None]:
    """Stream LLM response tokens. Yields text chunks."""
    provider = get_provider(config)
    body = provider.build_body(messages)

    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=30.0)) as client:
        async with client.stream("POST", provider.url, json=body, headers=provider.headers) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                raise RuntimeError(f"LLM API error {response.status_code}: {error_body.decode()}")
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    token = provider.parse_line(line)
                    if token:
                        yield token

async def complete_chat(config: dict, messages: list[dict]) -> str:
    """Non-streaming: collect full response."""
    result = []
    async for token in stream_chat(config, messages):
        result.append(token)
    return "".join(result)
```

- [ ] **Step 3: Create web search module**

```python
# backend/app/core/web_search.py
import httpx

async def tavily_search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Search via Tavily API. Returns list of {title, url, snippet, source}."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post("https://api.tavily.com/search", json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
        })
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for r in data.get("results", []):
            url = r.get("url", "")
            try:
                from urllib.parse import urlparse
                source = urlparse(url).hostname or ""
                source = source.replace("www.", "")
            except Exception:
                source = ""
            results.append({
                "title": r.get("title", "Untitled"),
                "url": url,
                "snippet": r.get("content", ""),
                "source": source,
            })
        return results
```

- [ ] **Step 4: Create SSE helper**

```python
# backend/app/core/sse.py
import json

def sse_event(event: str, data: dict | str) -> str:
    """Format a Server-Sent Event."""
    if isinstance(data, dict):
        data = json.dumps(data)
    return f"event: {event}\ndata: {data}\n\n"

def sse_token(token: str) -> str:
    return sse_event("token", {"text": token})

def sse_done(result: dict | None = None) -> str:
    return sse_event("done", result or {})

def sse_error(message: str) -> str:
    return sse_event("error", {"message": message})

def sse_progress(pct: int, message: str = "") -> str:
    return sse_event("progress", {"pct": pct, "message": message})
```

- [ ] **Step 5: Create LLM client tests**

```python
# backend/tests/test_llm_client.py
from app.core.llm_client import get_provider, _parse_openai_line, _parse_anthropic_line, _build_openai_body

def test_get_provider_openrouter():
    p = get_provider({"provider": "openrouter", "apiKey": "sk-test", "model": "gpt-4"})
    assert "openrouter.ai" in p.url
    assert "Bearer sk-test" in p.headers["Authorization"]

def test_get_provider_anthropic():
    p = get_provider({"provider": "anthropic", "apiKey": "sk-ant", "model": "claude-3"})
    assert "anthropic.com" in p.url
    assert p.headers["x-api-key"] == "sk-ant"

def test_parse_openai_line():
    line = 'data: {"choices":[{"delta":{"content":"hello"}}]}'
    assert _parse_openai_line(line) == "hello"
    assert _parse_openai_line("data: [DONE]") is None
    assert _parse_openai_line("not a data line") is None

def test_parse_anthropic_line():
    line = 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}'
    assert _parse_anthropic_line(line) == "hi"

def test_build_openai_body():
    body = _build_openai_body([{"role": "user", "content": "hi"}], "gpt-4")
    assert body["model"] == "gpt-4"
    assert body["stream"] is True
```

- [ ] **Step 6: Create web search tests**

```python
# backend/tests/test_web_search.py
from app.core.web_search import tavily_search

def test_tavily_search_returns_list():
    # Without a real API key, this is a smoke test for the function signature
    import asyncio
    results = asyncio.get_event_loop().run_until_complete(tavily_search("test", "fake-key", 1))
    assert isinstance(results, list)  # Will be empty without valid key
```

- [ ] **Step 7: Run tests and commit**

```bash
cd backend && python -m pytest tests/ -v
git add backend/ && git commit -m "feat(backend): add LLM client, web search, and SSE modules"
```

---

### Task 2: Conversation + Message Models + Migration

**Files:**
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/ingest_cache.py`
- Create: `backend/app/schemas/chat.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Conversation model**

```python
# backend/app/models/conversation.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(500), default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Create Message model**

```python
# backend/app/models/message.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user, assistant, system
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: Create IngestCache model**

```python
# backend/app/models/ingest_cache.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class IngestCache(Base):
    __tablename__ = "ingest_cache"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(500), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    written_paths: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Create Chat schemas**

```python
# backend/app/schemas/chat.py
import uuid
from datetime import datetime
from pydantic import BaseModel

class ConversationCreate(BaseModel):
    title: str = "New Conversation"

class ConversationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Update models __init__.py, generate migration**

Add imports for `Conversation`, `Message`, `IngestCache` to `__init__.py`.

```bash
alembic revision --autogenerate -m "add conversations, messages, ingest_cache tables"
alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add conversation, message, ingest_cache models"
```

---

### Task 3: Chat Service + Routes + SSE Streaming + Tests

**Files:**
- Create: `backend/app/services/chat_service.py`
- Create: `backend/app/api/chat.py`
- Create: `backend/app/api/streams.py`
- Create: `backend/tests/test_chat.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create chat service**

```python
# backend/app/services/chat_service.py
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.conversation import Conversation
from app.models.message import Message

async def create_conversation(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, title: str = "New Conversation") -> Conversation:
    conv = Conversation(id=uuid.uuid4(), project_id=project_id, user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

async def list_conversations(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).where(Conversation.project_id == project_id, Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())

async def get_conversation(db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

async def delete_conversation(db: AsyncSession, conv: Conversation) -> None:
    await db.delete(conv)
    await db.commit()

async def add_message(db: AsyncSession, conv_id: uuid.UUID, role: str, content: str) -> Message:
    msg = Message(id=uuid.uuid4(), conversation_id=conv_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg

async def list_messages(db: AsyncSession, conv_id: uuid.UUID, limit: int = 50) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc()).limit(limit)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Create chat routes**

```python
# backend/app/api/chat.py
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.chat import ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from app.services.chat_service import create_conversation, list_conversations, get_conversation, delete_conversation, add_message, list_messages
from app.api.deps import get_current_user, require_project_owner

router = APIRouter(tags=["chat"])

@router.post("/api/v1/projects/{project_id}/conversations", response_model=ConversationResponse, status_code=201)
async def create(project_id: uuid.UUID, req: ConversationCreate,
                 project: Project = Depends(require_project_owner), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await create_conversation(db, project.id, user.id, req.title)

@router.get("/api/v1/projects/{project_id}/conversations", response_model=list[ConversationResponse])
async def list_all(project_id: uuid.UUID, project: Project = Depends(require_project_owner),
                   user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
                   offset: int = 0, limit: int = 50):
    return await list_conversations(db, project.id, user.id, offset, limit)

@router.get("/api/v1/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(conv_id: uuid.UUID, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db), limit: int = 50):
    conv = await get_conversation(db, conv_id, user.id)
    return await list_messages(db, conv.id, limit)

@router.post("/api/v1/conversations/{conv_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(conv_id: uuid.UUID, req: MessageCreate,
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conv_id, user.id)
    return await add_message(db, conv.id, "user", req.content)

@router.delete("/api/v1/conversations/{conv_id}", status_code=204)
async def delete(conv_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conv_id, user.id)
    await delete_conversation(db, conv)
```

- [ ] **Step 3: Create SSE stream endpoints**

```python
# backend/app/api/streams.py
import uuid
from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, async_session
from app.models.project import Project
from app.models.user import User
from app.core.security import decode_token
from app.services.auth_service import get_user_by_id
from app.services.chat_service import get_conversation, add_message, list_messages
from app.services.config_service import get_effective_config
from app.core.llm_client import stream_chat
from app.core.sse import sse_token, sse_done, sse_error
from app.api.deps import require_project_owner

router = APIRouter(tags=["streams"])

async def _get_user_from_token(token: str) -> User | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        async with async_session() as db:
            return await get_user_by_id(db, uuid.UUID(payload["sub"]))
    except Exception:
        return None

@router.get("/api/v1/projects/{project_id}/stream/chat/{conv_id}")
async def stream_chat_sse(project_id: uuid.UUID, conv_id: uuid.UUID, token: str = Query(...)):
    """SSE endpoint for streaming LLM chat responses."""
    user = await _get_user_from_token(token)
    if not user:
        return StreamingResponse(iter([sse_error("Invalid token")]), media_type="text/event-stream")

    async def event_generator():
        try:
            async with async_session() as db:
                # Verify ownership
                from app.models.project import Project
                from sqlalchemy import select
                result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
                if not result.scalar_one_or_none():
                    yield sse_error("Not authorized")
                    return

                conv = await get_conversation(db, conv_id, user.id)
                messages = await list_messages(db, conv.id, limit=50)
                config = await get_effective_config(db, user.id)
                llm_config = config.get("llm_config", {})

                chat_messages = [{"role": m.role, "content": m.content} for m in messages]

                full_response = []
                async for chunk in stream_chat(llm_config, chat_messages):
                    full_response.append(chunk)
                    yield sse_token(chunk)

                # Save assistant message
                response_text = "".join(full_response)
                await add_message(db, conv.id, "assistant", response_text)

            yield sse_done({"chars": len(response_text)})
        except Exception as e:
            yield sse_error(str(e))

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 4: Register routers in main.py**

```python
from app.api.chat import router as chat_router
from app.api.streams import router as streams_router
app.include_router(chat_router)
app.include_router(streams_router)
```

- [ ] **Step 5: Create chat tests**

```python
# backend/tests/test_chat.py
async def _setup(client, email="chat@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Chat User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]

async def test_create_conversation(client):
    token, pid = await _setup(client)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/conversations", json={"title": "Test Chat"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["title"] == "Test Chat"

async def test_list_conversations(client):
    token, pid = await _setup(client, "list-chat@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/conversations", json={"title": "Chat 1"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/conversations", json={"title": "Chat 2"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/conversations", headers=h)
    assert len(resp.json()) == 2

async def test_send_and_get_messages(client):
    token, pid = await _setup(client, "msg@example.com")
    h = {"Authorization": f"Bearer {token}"}
    conv = await client.post(f"/api/v1/projects/{pid}/conversations", json={"title": "Msg Chat"}, headers=h)
    conv_id = conv.json()["id"]
    await client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=h)
    resp = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h)
    assert len(resp.json()) == 1
    assert resp.json()[0]["content"] == "Hello"
    assert resp.json()[0]["role"] == "user"

async def test_delete_conversation(client):
    token, pid = await _setup(client, "del-chat@example.com")
    h = {"Authorization": f"Bearer {token}"}
    conv = await client.post(f"/api/v1/projects/{pid}/conversations", json={"title": "Delete Me"}, headers=h)
    conv_id = conv.json()["id"]
    resp = await client.delete(f"/api/v1/conversations/{conv_id}", headers=h)
    assert resp.status_code == 204
```

- [ ] **Step 6: Run tests and commit**

```bash
cd backend && python -m pytest tests/ -v
git add backend/ && git commit -m "feat(backend): add chat service, routes, and SSE streaming"
```

---

### Task 4: Ingest Service + Routes + Tests

**Files:**
- Create: `backend/app/services/ingest_service.py`
- Create: `backend/app/api/ingest.py`
- Create: `backend/tests/test_ingest.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create ingest service**

Port the 2-step pipeline from `src/lib/ingest.ts`. Key elements:

```python
# backend/app/services/ingest_service.py
import re
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.page import Page
from app.models.source import Source
from app.models.ingest_cache import IngestCache
from app.core.llm_client import complete_chat
from app.core.background import update_task_status

FILE_BLOCK_REGEX = re.compile(r"---FILE:\s*([^\n-]+?)\s*---\n([\s\S]*?)---END FILE---")
REVIEW_BLOCK_REGEX = re.compile(r"---REVIEW:\s*(\w[\w-]*)\s*\|\s*(.+?)\s*---\n([\s\S]*?)---END REVIEW---")

# Analysis and generation prompts (port from TypeScript — see spec for full text)
# These are the key prompt templates from ingest.ts

def _build_analysis_prompt(purpose: str = "", index: str = "") -> str:
    prompt = """You are an expert research analyst. Read the source document and produce a structured analysis.

## Language Rule
- ALWAYS match the language of the source document.

Your analysis should cover:
## Key Entities - List people, organizations, products, datasets, tools mentioned.
## Key Concepts - List theories, methods, techniques, phenomena.
## Main Arguments & Findings - Core claims, evidence, strength of evidence.
## Connections to Existing Wiki - What existing pages does this relate to?
## Contradictions & Tensions - Conflicts with existing wiki content?
## Recommendations - What wiki pages should be created or updated?

Be thorough but concise. Focus on what's genuinely important."""
    if purpose:
        prompt += f"\n\n## Wiki Purpose\n{purpose}"
    if index:
        prompt += f"\n\n## Current Wiki Index\n{index}"
    return prompt

def _build_generation_prompt(schema: str, purpose: str, index: str, source_filename: str, overview: str = "") -> str:
    prompt = f"""You are a wiki maintainer. Based on the analysis provided, generate wiki files.

## Language Rule
- ALWAYS match the language of the source document.

## Source File
The original source file is: **{source_filename}**
All wiki pages MUST include this filename in their frontmatter `sources` field.

## Output Format
Output each wiki file as:
---FILE: wiki/path/to/file.md---
(complete file content with YAML frontmatter)
---END FILE---

Generate:
1. Source summary at wiki/sources/{source_filename.rsplit('.', 1)[0]}.md
2. Entity pages in wiki/entities/
3. Concept pages in wiki/concepts/
4. Updated wiki/index.md
5. Log entry for wiki/log.md
6. Updated wiki/overview.md

## Frontmatter (every page):
---
type: source | entity | concept | comparison | query | synthesis
title: Human-readable title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
sources: ["{source_filename}"]
---

Use [[wikilink]] syntax for cross-references. Use kebab-case filenames.

## Review Items
After FILE blocks, output REVIEW blocks for items needing human judgment:
---REVIEW: type | Title---
Description
OPTIONS: Create Page | Skip
PAGES: wiki/page1.md, wiki/page2.md
SEARCH: query1 | query2
---END REVIEW---

Types: contradiction, duplicate, missing-page, suggestion"""
    if purpose:
        prompt += f"\n\n## Wiki Purpose\n{purpose}"
    if schema:
        prompt += f"\n\n## Wiki Schema\n{schema}"
    if index:
        prompt += f"\n\n## Current Wiki Index\n{index}"
    if overview:
        prompt += f"\n\n## Current Overview\n{overview}"
    return prompt

def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    """Parse ---FILE: path--- ... ---END FILE--- blocks. Returns [(path, content)]."""
    return FILE_BLOCK_REGEX.findall(text)

def parse_review_blocks(text: str, source_path: str = "") -> list[dict]:
    """Parse ---REVIEW: type | title--- ... ---END REVIEW--- blocks."""
    reviews = []
    allowed_types = {"contradiction", "duplicate", "missing-page", "suggestion", "confirm"}
    for match in REVIEW_BLOCK_REGEX.finditer(text):
        rtype = match.group(1).lower()
        if rtype not in allowed_types:
            rtype = "confirm"
        title = match.group(2).strip()
        body = match.group(3).strip()

        # Parse OPTIONS
        options_match = re.search(r"^OPTIONS:\s*(.+)$", body, re.MULTILINE)
        options = [{"label": o.strip(), "action": o.strip()} for o in options_match.group(1).split("|")] if options_match else [{"label": "Approve", "action": "Approve"}, {"label": "Skip", "action": "Skip"}]

        # Parse PAGES
        pages_match = re.search(r"^PAGES:\s*(.+)$", body, re.MULTILINE)
        affected_pages = [p.strip() for p in pages_match.group(1).split(",")] if pages_match else []

        # Parse SEARCH
        search_match = re.search(r"^SEARCH:\s*(.+)$", body, re.MULTILINE)
        search_queries = [q.strip() for q in search_match.group(1).split("|") if q.strip()] if search_match else []

        # Description = body without metadata lines
        description = re.sub(r"^(OPTIONS|PAGES|SEARCH):.*$", "", body, flags=re.MULTILINE).strip()

        reviews.append({
            "type": rtype, "title": title, "description": description,
            "source_path": source_path, "affected_pages": affected_pages,
            "search_queries": search_queries, "options": options,
        })
    return reviews

async def run_ingest(task_id: uuid.UUID, project_id: uuid.UUID, source_id: uuid.UUID, llm_config: dict):
    """Background ingest: analysis → generation → write pages → parse reviews."""
    from app.db.session import async_session
    from app.services.page_service import create_page, get_page_by_path, update_page

    try:
        await update_task_status(task_id, "running", progress=5)

        async with async_session() as db:
            # Load source
            source = await db.execute(select(Source).where(Source.id == source_id))
            source = source.scalar_one_or_none()
            if not source or not source.extracted_text:
                await update_task_status(task_id, "failed", error="Source not found or not extracted")
                return

            # Check cache
            cache = await db.execute(select(IngestCache).where(
                IngestCache.project_id == project_id, IngestCache.source_filename == source.filename
            ))
            cache_entry = cache.scalar_one_or_none()
            content_hash = hashlib.sha256(source.extracted_text.encode()).hexdigest()
            if cache_entry and cache_entry.content_hash == content_hash:
                await update_task_status(task_id, "completed", progress=100, result={"skipped": True, "reason": "unchanged"})
                return

            # Load project context
            from app.models.project import Project
            proj = await db.execute(select(Project).where(Project.id == project_id))
            proj = proj.scalar_one()

            # Load index and overview pages
            index_page = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == "index.md"))
            index_content = index_page.scalar_one_or_none()
            index_text = index_content.content if index_content else ""

            overview_page = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == "overview.md"))
            overview_content = overview_page.scalar_one_or_none()
            overview_text = overview_content.content if overview_content else ""

            source_text = source.extracted_text[:50000]  # Truncate for context window

        await update_task_status(task_id, "running", progress=15)

        # Step 1: Analysis
        analysis_prompt = _build_analysis_prompt(proj.purpose, index_text)
        analysis = await complete_chat(llm_config, [
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": source_text},
        ])

        await update_task_status(task_id, "running", progress=50)

        # Step 2: Generation
        gen_prompt = _build_generation_prompt(proj.schema_text, proj.purpose, index_text, source.filename, overview_text)
        generation = await complete_chat(llm_config, [
            {"role": "system", "content": gen_prompt},
            {"role": "user", "content": f"## Analysis\n{analysis}\n\n## Original Source\n{source_text}"},
        ])

        await update_task_status(task_id, "running", progress=80)

        # Step 3: Parse and write FILE blocks
        file_blocks = parse_file_blocks(generation)
        written_paths = []

        async with async_session() as db:
            for path, content in file_blocks:
                path = path.strip()
                if not path.startswith("wiki/"):
                    continue

                # Determine page type from path
                page_type = "entity"
                if "/sources/" in path:
                    page_type = "source"
                elif "/concepts/" in path:
                    page_type = "concept"
                elif "/queries/" in path:
                    page_type = "query"
                elif "/comparisons/" in path:
                    page_type = "comparison"
                elif "/synthesis/" in path:
                    page_type = "synthesis"

                # Extract title from content
                title = path.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ").title()
                for line in content.split("\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

                # Create or update page
                existing = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == path))
                existing_page = existing.scalar_one_or_none()
                if existing_page:
                    if path.endswith("log.md"):
                        existing_page.content = content.strip() + "\n\n" + existing_page.content
                    else:
                        existing_page.content = content.strip()
                    existing_page.frontmatter = {"sources": [source.filename]}
                else:
                    new_page = Page(
                        id=uuid.uuid4(), project_id=project_id, path=path,
                        type=page_type, title=title, content=content.strip(),
                        frontmatter={"sources": [source.filename]},
                    )
                    db.add(new_page)
                written_paths.append(path)

            # Update ingest cache
            if cache_entry:
                cache_entry.content_hash = content_hash
                cache_entry.written_paths = written_paths
            else:
                db.add(IngestCache(
                    project_id=project_id, source_filename=source.filename,
                    content_hash=content_hash, written_paths=written_paths,
                ))

            await db.commit()

        # Step 4: Parse review blocks
        reviews = parse_review_blocks(generation, source.filename if source else "")

        await update_task_status(task_id, "completed", progress=100, result={
            "pages_written": len(written_paths),
            "reviews_found": len(reviews),
            "written_paths": written_paths,
            "reviews": reviews,
        })

    except Exception as e:
        await update_task_status(task_id, "failed", error=str(e))
```

- [ ] **Step 2: Create ingest routes**

```python
# backend/app/api/ingest.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.project import Project
from app.models.task import BackgroundTask
from app.schemas.task import TaskResponse
from app.core.background import create_task, dispatch_background, cancel_task
from app.services.config_service import get_effective_config
from app.services.ingest_service import run_ingest
from app.api.deps import get_current_user, require_project_owner
from app.models.user import User
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/projects/{project_id}/ingest", tags=["ingest"])

class IngestRequest(BaseModel):
    source_id: uuid.UUID

@router.post("", response_model=TaskResponse, status_code=202)
async def start_ingest(project_id: uuid.UUID, req: IngestRequest,
                       project: Project = Depends(require_project_owner),
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    config = await get_effective_config(db, user.id)
    llm_config = config.get("llm_config", {})
    if not llm_config.get("apiKey"):
        raise HTTPException(status_code=400, detail="No LLM API key configured")
    task = await create_task(db, project.id, user.id, "ingest", {"source_id": str(req.source_id)})
    dispatch_background(task.id, run_ingest(task.id, project.id, req.source_id, llm_config))
    return task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_status(project_id: uuid.UUID, task_id: uuid.UUID,
                     project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == task_id, BackgroundTask.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/cancel", status_code=204)
async def cancel(project_id: uuid.UUID, task_id: uuid.UUID,
                 project: Project = Depends(require_project_owner)):
    if not cancel_task(task_id):
        raise HTTPException(status_code=404, detail="Task not running")
```

- [ ] **Step 3: Register router, create tests**

Register in main.py:
```python
from app.api.ingest import router as ingest_router
app.include_router(ingest_router)
```

```python
# backend/tests/test_ingest.py
from app.services.ingest_service import parse_file_blocks, parse_review_blocks

def test_parse_file_blocks():
    text = """Some text
---FILE: wiki/entities/ml.md---
# Machine Learning
Content here
---END FILE---

---FILE: wiki/concepts/nn.md---
# Neural Networks
More content
---END FILE---
"""
    blocks = parse_file_blocks(text)
    assert len(blocks) == 2
    assert blocks[0][0].strip() == "wiki/entities/ml.md"
    assert "Machine Learning" in blocks[0][1]

def test_parse_review_blocks():
    text = """
---REVIEW: contradiction | Conflicting Claim---
This contradicts existing wiki content.
OPTIONS: Create Page | Skip
PAGES: wiki/entities/ml.md
SEARCH: machine learning contradiction | deep learning vs ml
---END REVIEW---
"""
    reviews = parse_review_blocks(text, "source.pdf")
    assert len(reviews) == 1
    assert reviews[0]["type"] == "contradiction"
    assert reviews[0]["title"] == "Conflicting Claim"
    assert len(reviews[0]["options"]) == 2
    assert len(reviews[0]["search_queries"]) == 2

def test_parse_empty():
    assert parse_file_blocks("no blocks here") == []
    assert parse_review_blocks("no reviews") == []
```

- [ ] **Step 4: Run tests and commit**

```bash
cd backend && python -m pytest tests/ -v
git add backend/ && git commit -m "feat(backend): add ingest pipeline with 2-step LLM analysis and generation"
```

---

### Task 5: Research Service + Routes

**Files:**
- Create: `backend/app/services/research_service.py`
- Create: `backend/app/api/research.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create research service**

```python
# backend/app/services/research_service.py
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.page import Page
from app.core.llm_client import complete_chat
from app.core.web_search import tavily_search
from app.core.background import update_task_status

THINK_BLOCK_REGEX = re.compile(r"<think(?:ing)?>\s*[\s\S]*?</think(?:ing)?>\s*", re.IGNORECASE)

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:50]

async def run_research(task_id: uuid.UUID, project_id: uuid.UUID, topic: str, search_queries: list[str], llm_config: dict, search_api_key: str):
    """Background research: web search → LLM synthesis → save as wiki page."""
    from app.db.session import async_session

    try:
        await update_task_status(task_id, "running", progress=10)

        # Step 1: Web search
        queries = search_queries if search_queries else [topic]
        all_results = []
        seen_urls = set()
        for query in queries:
            results = await tavily_search(query, search_api_key, max_results=5)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)

        await update_task_status(task_id, "running", progress=40)

        # Load wiki index for cross-referencing
        async with async_session() as db:
            index_page = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == "index.md"))
            index_content = index_page.scalar_one_or_none()
            index_text = index_content.content if index_content else ""

        # Step 2: LLM synthesis
        system_prompt = f"""You are a research assistant. Synthesize the web search results into a comprehensive wiki page.

## Language Rule
- ALWAYS match the language of the research topic.

## Cross-referencing
- Use [[wikilink]] syntax to link to existing wiki pages.
- Organize into clear sections with headings.
- Cite web sources using [N] notation.
- Note contradictions or gaps.
- Neutral, encyclopedic tone.

## Wiki Index
{index_text}"""

        results_text = "\n\n".join(
            f"[{i+1}] **{r['title']}** ({r['source']})\n{r['snippet']}"
            for i, r in enumerate(all_results)
        )

        synthesis = await complete_chat(llm_config, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research topic: **{topic}**\n\n## Web Search Results\n\n{results_text}\n\nSynthesize into a wiki page."},
        ])

        await update_task_status(task_id, "running", progress=80)

        # Clean thinking blocks
        synthesis = THINK_BLOCK_REGEX.sub("", synthesis).strip()

        # Step 3: Save to wiki
        slug = _slugify(topic)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"research-{slug}-{date_str}.md"
        path = f"wiki/queries/{filename}"

        references = "\n".join(f"- [{i+1}] [{r['title']}]({r['url']}) ({r['source']})" for i, r in enumerate(all_results))

        page_content = f"""---
type: query
title: "Research: {topic}"
created: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
origin: deep-research
tags: [research]
sources: []
---

{synthesis}

## References

{references}
"""

        async with async_session() as db:
            page = Page(
                id=uuid.uuid4(), project_id=project_id, path=path,
                type="query", title=f"Research: {topic}", content=page_content,
                frontmatter={"origin": "deep-research", "tags": ["research"]},
            )
            db.add(page)
            await db.commit()

        await update_task_status(task_id, "completed", progress=100, result={
            "path": path,
            "search_results": len(all_results),
            "synthesis_chars": len(synthesis),
        })

    except Exception as e:
        await update_task_status(task_id, "failed", error=str(e))
```

- [ ] **Step 2: Create research routes**

```python
# backend/app/api/research.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.project import Project
from app.models.task import BackgroundTask
from app.models.user import User
from app.schemas.task import TaskResponse
from app.core.background import create_task, dispatch_background
from app.services.config_service import get_effective_config
from app.services.research_service import run_research
from app.api.deps import get_current_user, require_project_owner
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/projects/{project_id}/research", tags=["research"])

class ResearchRequest(BaseModel):
    topic: str
    search_queries: list[str] = []

@router.post("", response_model=TaskResponse, status_code=202)
async def start_research(project_id: uuid.UUID, req: ResearchRequest,
                         project: Project = Depends(require_project_owner),
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    config = await get_effective_config(db, user.id)
    llm_config = config.get("llm_config", {})
    search_config = config.get("search_config", {})
    search_key = search_config.get("apiKey", "")
    if not llm_config.get("apiKey"):
        raise HTTPException(status_code=400, detail="No LLM API key configured")
    task = await create_task(db, project.id, user.id, "deep_research", {"topic": req.topic})
    dispatch_background(task.id, run_research(task.id, project.id, req.topic, req.search_queries, llm_config, search_key))
    return task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_status(project_id: uuid.UUID, task_id: uuid.UUID,
                     project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == task_id, BackgroundTask.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

- [ ] **Step 3: Register router**

```python
from app.api.research import router as research_router
app.include_router(research_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add deep research with web search and LLM synthesis"
```

---

### Task 6: Full Test Suite + Verification

- [ ] **Step 1: Run all tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: ~60+ tests all passing.

- [ ] **Step 2: Final commit**

```bash
git add -A backend/ && git commit -m "feat(backend): complete Plan 3 — LLM, chat, ingest, research, SSE"
```

---

## Plan Summary

| Task | What | New Tests |
|------|------|-----------|
| 1 | LLM client + web search + SSE helper | 6 |
| 2 | Conversation + Message + IngestCache models | 0 |
| 3 | Chat service + routes + SSE streaming | 4 |
| 4 | Ingest service + routes | 3 |
| 5 | Research service + routes | 0 |
| 6 | Full test suite verification | 0 |

**After this plan:** Backend has LLM proxy, chat, ingest pipeline, deep research, and SSE streaming. Ready for Plan 4 (Graph, Search, Lint, Review).
