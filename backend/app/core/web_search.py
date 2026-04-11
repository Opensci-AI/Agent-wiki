"""Tavily web search integration."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(
    query: str,
    api_key: str,
    max_results: int = 5,
) -> list[dict]:
    """Run an advanced Tavily search and return normalised results.

    Each result dict has keys: title, url, snippet, source.
    Returns an empty list on error (non-200 or network failure).
    """
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(TAVILY_SEARCH_URL, json=payload)
            if resp.status_code != 200:
                return []
            data = resp.json()
    except (httpx.HTTPError, Exception):
        return []

    results: list[dict] = []
    for item in data.get("results", []):
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": urlparse(item.get("url", "")).hostname or "",
            }
        )
    return results
