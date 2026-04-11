import asyncio
from app.core.web_search import tavily_search


def test_tavily_returns_list():
    """Tavily search with a fake key should return an empty list (non-200)."""
    results = asyncio.get_event_loop().run_until_complete(
        tavily_search("test", "fake-key", 1)
    )
    assert isinstance(results, list)
