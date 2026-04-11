from app.core.llm_client import get_provider, _parse_openai_line, _parse_anthropic_line, _build_openai_body


def test_get_provider_openrouter():
    p = get_provider({"provider": "openrouter", "apiKey": "sk-test", "model": "gpt-4"})
    assert "openrouter.ai" in p.url


def test_get_provider_anthropic():
    p = get_provider({"provider": "anthropic", "apiKey": "sk-ant", "model": "claude-3"})
    assert "anthropic.com" in p.url


def test_get_provider_openai():
    p = get_provider({"provider": "openai", "apiKey": "sk-test", "model": "gpt-4"})
    assert "openai.com" in p.url


def test_get_provider_google():
    p = get_provider({"provider": "google", "apiKey": "key", "model": "gemini-pro"})
    assert "googleapis.com" in p.url
    assert "gemini-pro" in p.url


def test_get_provider_ollama():
    p = get_provider({"provider": "ollama", "model": "llama3"})
    assert "localhost:11434" in p.url


def test_get_provider_custom():
    p = get_provider({"provider": "custom", "baseUrl": "http://myhost:9000"})
    assert "myhost:9000" in p.url


def test_parse_openai_line_token():
    assert _parse_openai_line('data: {"choices":[{"delta":{"content":"hello"}}]}') == "hello"


def test_parse_openai_line_done():
    assert _parse_openai_line("data: [DONE]") is None


def test_parse_openai_line_not_data():
    assert _parse_openai_line("not data") is None


def test_parse_openai_line_no_content():
    assert _parse_openai_line('data: {"choices":[{"delta":{}}]}') is None


def test_parse_anthropic_line():
    assert _parse_anthropic_line('data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}') == "hi"


def test_parse_anthropic_line_other_event():
    assert _parse_anthropic_line('data: {"type":"message_start"}') is None


def test_build_openai_body():
    body = _build_openai_body([{"role": "user", "content": "hi"}], "gpt-4")
    assert body["model"] == "gpt-4"
    assert body["stream"] is True
    assert body["messages"][0]["content"] == "hi"
