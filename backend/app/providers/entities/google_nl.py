"""Premium entity extraction via Google Cloud Natural Language analyzeEntities.

Returns Google's native salience scores. Billing is per 1,000 Unicode chars,
rounded up per request — unit accounting is handled by the orchestrator before
this is called.
"""
from __future__ import annotations

import httpx

from ...config import settings
from ...schemas import EntityResult
from ..base import ProviderUnavailable, QuotaExceeded

ENDPOINT = "https://language.googleapis.com/v1/documents:analyzeEntities"


class GoogleNLProvider:
    name = "google_nl"

    def configured(self) -> bool:
        return bool(settings.google_nl_api_key)

    async def extract(self, text: str, language: str, top_n: int = 10) -> list[EntityResult]:
        if not self.configured():
            raise ProviderUnavailable("Google NL API not configured")

        payload = {
            "document": {"type": "PLAIN_TEXT", "content": text},
            "encodingType": "UTF8",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                ENDPOINT, params={"key": settings.google_nl_api_key}, json=payload
            )
        if resp.status_code == 429:
            raise QuotaExceeded("Google NL quota exceeded")
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"Google NL {resp.status_code}")
        resp.raise_for_status()

        entities = resp.json().get("entities", [])
        out: list[EntityResult] = []
        for e in entities:
            out.append(EntityResult(
                name=e.get("name", ""),
                type=e.get("type", ""),
                salience=round(float(e.get("salience", 0.0)), 4),
                mentions=len(e.get("mentions", [])) or 1,
                source="google_nl",
            ))
        out.sort(key=lambda x: x.salience, reverse=True)
        return out[:top_n]
