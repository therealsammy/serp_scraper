"""Google results via the Apify 'Google Search Results Scraper' actor.

Apify runs the scraping + anti-bot infrastructure on their managed platform and
exposes it as an API. From our side this is just an authenticated HTTP call that
returns real Google organic results — same shape as our other providers.
"""
from __future__ import annotations

import httpx

from ..config import settings
from ..schemas import GeoOptions, SearchResult
from ..services.uule import encode_uule
from .base import ProviderUnavailable, QuotaExceeded

# run-sync-get-dataset-items runs the actor and returns its dataset in one call.
ACTOR = "apify~google-search-scraper"
ENDPOINT = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"


class ApifyGoogleProvider:
    name = "apify"

    def configured(self) -> bool:
        return bool(settings.apify_api_token)

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        if not self.configured():
            raise ProviderUnavailable("Apify token not configured")

        geo = geo or GeoOptions()
        payload = {
            "queries": query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": min(max(count, 1), 100),
            "countryCode": geo.country,
            "searchLanguage": geo.language,
            "languageCode": geo.language,
        }
        # City-level targeting: encode the plain location string to a UULE token.
        if geo.location:
            payload["locationUule"] = encode_uule(geo.location)
        # Actor runs can take a little while; allow generous timeout.
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                ENDPOINT,
                params={"token": settings.apify_api_token},
                json=payload,
            )
        if resp.status_code in (401, 403):
            raise ProviderUnavailable("Apify token rejected")
        if resp.status_code == 429:
            raise QuotaExceeded("Apify rate/credit limit hit")
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"Apify {resp.status_code}")
        resp.raise_for_status()

        # Dataset is a list of page objects; organic results live under
        # "organicResults" on each page.
        pages = resp.json()
        results: list[SearchResult] = []
        for page in pages:
            for item in page.get("organicResults", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", "") or item.get("snippet", ""),
                        rank=len(results) + 1,
                        source_provider=self.name,
                    )
                )
                if len(results) >= count:
                    return results
        return results
