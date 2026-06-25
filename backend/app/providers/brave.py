"""Brave Search API provider."""
from __future__ import annotations

import httpx

from ..config import settings
from ..schemas import GeoOptions, SearchResult
from .base import ProviderUnavailable, QuotaExceeded

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider:
    name = "brave"

    def configured(self) -> bool:
        return bool(settings.brave_api_key)

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        if not self.configured():
            raise ProviderUnavailable("Brave API not configured")

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": settings.brave_api_key,
        }
        params = {"q": query, "count": min(count, 20)}
        if geo:  # Brave supports country-level targeting
            params["country"] = geo.country
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(ENDPOINT, headers=headers, params=params)
        if resp.status_code == 429:
            raise QuotaExceeded("Brave quota exceeded")
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"Brave {resp.status_code}")
        resp.raise_for_status()

        web = resp.json().get("web", {}).get("results", [])
        results: list[SearchResult] = []
        for i, item in enumerate(web[:count]):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    rank=i + 1,
                    source_provider=self.name,
                )
            )
        return results
