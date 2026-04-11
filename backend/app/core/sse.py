"""SSE event formatting helpers."""

from __future__ import annotations

import json


def sse_event(event: str, data: dict | str) -> str:
    """Format an SSE event with an event type and JSON/string data."""
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def sse_token(token: str) -> str:
    """Format a token SSE event."""
    return sse_event("token", {"text": token})


def sse_done() -> str:
    """Format a done SSE event."""
    return sse_event("done", {"status": "complete"})


def sse_error(msg: str) -> str:
    """Format an error SSE event."""
    return sse_event("error", {"message": msg})


def sse_progress(pct: int, msg: str) -> str:
    """Format a progress SSE event."""
    return sse_event("progress", {"percent": pct, "message": msg})
