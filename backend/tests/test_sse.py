import json
from app.core.sse import sse_event, sse_token, sse_done, sse_error, sse_progress


def test_sse_event_dict():
    result = sse_event("test", {"key": "value"})
    assert result.startswith("event: test\n")
    assert '"key": "value"' in result
    assert result.endswith("\n\n")


def test_sse_event_string():
    result = sse_event("test", "hello")
    assert "data: hello\n" in result


def test_sse_token():
    result = sse_token("hello")
    assert "event: token\n" in result
    data = json.loads(result.split("data: ")[1].strip())
    assert data["text"] == "hello"


def test_sse_done():
    result = sse_done()
    assert "event: done\n" in result
    data = json.loads(result.split("data: ")[1].strip())
    assert data["status"] == "complete"


def test_sse_error():
    result = sse_error("oops")
    assert "event: error\n" in result
    data = json.loads(result.split("data: ")[1].strip())
    assert data["message"] == "oops"


def test_sse_progress():
    result = sse_progress(50, "halfway")
    assert "event: progress\n" in result
    data = json.loads(result.split("data: ")[1].strip())
    assert data["percent"] == 50
    assert data["message"] == "halfway"
