"""Brave Search API client."""

import json
from typing import Any

import httpx
from app.config import get_settings


class BraveSearchError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def brave_search(query: str, count: int = 10) -> dict[str, Any]:
    """Execute a Brave Search query and return sanitized results."""
    settings = get_settings()

    if not settings.brave_search_api_key or settings.brave_search_api_key.startswith("BSA-your-"):
        raise BraveSearchError("Brave Search API key is not configured", status_code=401)

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_search_api_key,
    }
    params = {
        "q": query,
        "count": min(count, 20),
        "search_lang": "en",
    }

    timeout = httpx.Timeout(settings.search_timeout)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        return _sanitize_search_results(data)
    except httpx.HTTPStatusError as e:
        raise BraveSearchError(
            f"Brave Search HTTP error: {e.response.status_code}",
            status_code=e.response.status_code,
        )
    except httpx.TimeoutException:
        raise BraveSearchError("Brave Search request timed out")
    except Exception as e:
        raise BraveSearchError(f"Brave Search error: {str(e)}")


async def fetch_page_content(url: str) -> str:
    """Fetch public page content. Only use for pages deemed necessary by ingestion decision."""
    settings = get_settings()

    if not settings.page_fetch_enabled:
        raise BraveSearchError("Page fetching is disabled in configuration")

    timeout = httpx.Timeout(settings.search_timeout)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; F1Analyzer/1.0; +research tool)",
                    "Accept": "text/html,text/plain",
                },
                follow_redirects=True,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type or "text/plain" in content_type:
                text = response.text
                if len(text) > 50000:
                    text = text[:50000]
                return text
            raise BraveSearchError(f"Unsupported content type: {content_type}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 401):
            raise BraveSearchError(f"Page access restricted: {e.response.status_code}", e.response.status_code)
        raise BraveSearchError(f"Page fetch error: {e.response.status_code}", e.response.status_code)
    except httpx.TimeoutException:
        raise BraveSearchError("Page fetch timed out")


def _sanitize_search_results(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract only metadata we persist from Brave results."""
    results = []
    web = raw.get("web", {})
    for item in web.get("results", []):
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "age": item.get("age", ""),
            "page_age": item.get("page_age", ""),
        })

    return {
        "query": raw.get("query", {}).get("original", ""),
        "total_results": web.get("total_results", 0) if isinstance(web, dict) else 0,
        "results": results,
    }
