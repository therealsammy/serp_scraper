"""Premium entity extraction via the Apify LangExtract actor (LLM-based).

Uses the same run-sync-get-dataset-items pattern as providers/apify.py. LangExtract
is schema-driven; we pass an extraction schema that asks for entities plus a
salience (0..1) attribute, so the LLM ranks importance. Salience here is an LLM
judgment, not a deterministic score.

NOTE: the actor's exact input field names are verified during integration; the
orchestrator falls back to spaCy if this call fails, so a schema mismatch degrades
gracefully rather than breaking the feature.
"""
from __future__ import annotations

import json

import httpx

from ...config import settings
from ...schemas import EntityResult
from ..base import ProviderUnavailable, QuotaExceeded

ACTOR = "vivianferreira~langextract-structured-data-extractor"
ENDPOINT = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"

_SYSTEM_PROMPT = (
    "Extract the most important named entities (people, organizations, locations, "
    "products, events). For each, return its name, type, and a salience score from "
    "0 to 1 indicating how central it is to the overall text."
)

# The actor's `schema` field is a JSON STRING describing the desired output.
_SCHEMA = json.dumps({
    "entities": [
        {"name": "string", "type": "string", "salience": "number (0-1)"}
    ]
})


class LangExtractProvider:
    name = "langextract"

    def configured(self) -> bool:
        return bool(settings.apify_api_token and settings.langextract_llm_key)

    async def extract(self, text: str, language: str, top_n: int = 10) -> list[EntityResult]:
        if not self.configured():
            raise ProviderUnavailable("LangExtract not configured")

        payload = {
            "text": text,
            "provider": settings.langextract_llm_provider,
            "apiKey": settings.langextract_llm_key,
            "model": settings.langextract_model,
            "systemPrompt": _SYSTEM_PROMPT,
            "schema": _SCHEMA,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                ENDPOINT, params={"token": settings.apify_api_token}, json=payload
            )
        if resp.status_code in (401, 403):
            raise ProviderUnavailable("Apify/LangExtract token rejected")
        if resp.status_code == 429:
            raise QuotaExceeded("Apify rate/credit limit hit")
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"LangExtract {resp.status_code}")
        resp.raise_for_status()

        return self._parse(resp.json(), top_n)

    def _parse(self, dataset, top_n: int) -> list[EntityResult]:
        """Flexibly pull entities out of the actor's dataset rows."""
        out: list[EntityResult] = []
        for row in dataset:
            # Entities may live under various keys depending on the schema run.
            ents = (
                row.get("entities")
                or row.get("extractions")
                or (row.get("data", {}) or {}).get("entities")
                or []
            )
            for e in ents:
                if not isinstance(e, dict):
                    continue
                name = e.get("name") or e.get("text") or e.get("value") or ""
                if not name:
                    continue
                try:
                    sal = float(e.get("salience", e.get("score", 0.0)) or 0.0)
                except (TypeError, ValueError):
                    sal = 0.0
                out.append(EntityResult(
                    name=str(name).strip(),
                    type=str(e.get("type") or e.get("class") or "").upper(),
                    salience=round(sal, 4),
                    mentions=int(e.get("mentions", 1) or 1),
                    source="langextract",
                ))
        out.sort(key=lambda x: x.salience, reverse=True)
        return out[:top_n]
