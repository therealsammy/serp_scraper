"""Multi-vendor SERP fallback with per-key daily caps and circuit breaker.

One legitimate account per vendor — cross-provider rotation, ordered by most
generous free tier first. On quota/5xx a vendor is marked unhealthy for a short
TTL and we fail over to the next.
"""
from __future__ import annotations

import httpx

from ..config import settings
from ..db import redis_client
from ..schemas import GeoOptions, SearchResult
from .base import ProviderError, ProviderUnavailable, QuotaExceeded

BREAKER_TTL = 300  # seconds a vendor stays "open" after failure


class _Vendor:
    def __init__(self, name: str, key: str):
        self.name = name
        self.key = key

    def configured(self) -> bool:
        return bool(self.key)

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        raise NotImplementedError


class _Serper(_Vendor):
    async def search(self, query, count, geo=None) -> list[SearchResult]:
        geo = geo or GeoOptions()
        body = {"q": query, "num": count, "gl": geo.country, "hl": geo.language}
        if geo.location:
            body["location"] = geo.location
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.key, "Content-Type": "application/json"},
                json=body,
            )
        _check(resp, self.name)
        organic = resp.json().get("organic", [])
        return _normalize(organic, count, self.name, "link", "snippet")


class _ScaleSerp(_Vendor):
    async def search(self, query, count, geo=None) -> list[SearchResult]:
        geo = geo or GeoOptions()
        params = {"api_key": self.key, "q": query, "num": count,
                  "gl": geo.country, "hl": geo.language}
        if geo.location:
            params["location"] = geo.location
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.scaleserp.com/search", params=params)
        _check(resp, self.name)
        organic = resp.json().get("organic_results", [])
        return _normalize(organic, count, self.name, "link", "snippet")


class _SerpApi(_Vendor):
    async def search(self, query, count, geo=None) -> list[SearchResult]:
        geo = geo or GeoOptions()
        params = {"api_key": self.key, "q": query, "num": count, "engine": "google",
                  "gl": geo.country, "hl": geo.language}
        if geo.location:
            params["location"] = geo.location
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://serpapi.com/search", params=params)
        _check(resp, self.name)
        organic = resp.json().get("organic_results", [])
        return _normalize(organic, count, self.name, "link", "snippet")


def _check(resp: httpx.Response, name: str) -> None:
    if resp.status_code == 429:
        raise QuotaExceeded(f"{name} quota exceeded")
    if resp.status_code >= 500:
        raise ProviderUnavailable(f"{name} {resp.status_code}")
    resp.raise_for_status()


def _normalize(items, count, name, url_key, snip_key) -> list[SearchResult]:
    out: list[SearchResult] = []
    for i, item in enumerate(items[:count]):
        out.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get(url_key, ""),
                snippet=item.get(snip_key, ""),
                rank=i + 1,
                source_provider=name,
            )
        )
    return out


class SerpFallbackProvider:
    """Tries each configured vendor in priority order, respecting caps/breaker."""

    name = "serp_fallback"

    def __init__(self) -> None:
        # Priority order: most generous free tier first.
        self.vendors: list[_Vendor] = [
            _Serper("serper", settings.serper_api_key),
            _ScaleSerp("scaleserp", settings.scaleserp_api_key),
            _SerpApi("serpapi", settings.serpapi_api_key),
        ]
        self.caps: dict[str, int] = settings.limits.get("fallback", {})

    def configured(self) -> bool:
        return any(v.configured() for v in self.vendors)

    async def _breaker_open(self, name: str) -> bool:
        return await redis_client.exists(f"breaker:{name}") == 1

    async def _trip_breaker(self, name: str) -> None:
        await redis_client.set(f"breaker:{name}", "1", ex=BREAKER_TTL)

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        from ..services.quota import day_key, incr_capped  # local import: avoid cycle

        last_err: Exception | None = None
        for v in self.vendors:
            if not v.configured():
                continue
            if await self._breaker_open(v.name):
                continue
            cap = self.caps.get(v.name, 0)
            key = f"serp:{v.name}:{day_key()}"
            if not await incr_capped(key, cap):
                continue  # daily cap hit for this vendor
            try:
                results = await v.search(query, count, geo)
                if results:
                    return results
            except (QuotaExceeded, ProviderUnavailable) as exc:
                last_err = exc
                await self._trip_breaker(v.name)
                continue
            except Exception as exc:  # network/parse
                last_err = exc
                await self._trip_breaker(v.name)
                continue
        raise ProviderError(
            f"All fallback SERP vendors exhausted/unavailable: {last_err}"
        )
