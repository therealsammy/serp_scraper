"""Tier-aware entity extraction with character-based unit accounting.

  anonymous tier  -> spaCy (free, computed salience)
  registered tier -> premium under caps:
                       Google NL   (native salience; monthly UNIT cap)
                       LangExtract (LLM salience; daily REQUEST cap)
                     then spaCy on cap/unconfigured/error
"""
from __future__ import annotations

import math

from ...config import settings
from ...schemas import EntityResult
from ...services.quota import day_key, incr_by_capped, incr_capped, month_key
from ..base import ProviderError
from .google_nl import GoogleNLProvider
from .langextract import LangExtractProvider
from .spacy_provider import SpacyProvider

_spacy = SpacyProvider()
_google = GoogleNLProvider()
_langextract = LangExtractProvider()


def _ecfg() -> dict:
    return settings.limits.get("entities", {})


async def _spacy_result(text: str, language: str):
    return "spacy", 0, await _spacy.extract(text, language)


async def extract_entities(
    text: str, language: str, tier: str
) -> tuple[str, int, list[EntityResult]]:
    """Returns (source, units_charged, entities)."""
    cfg = _ecfg()
    text = (text or "").strip()
    if not text:
        return "spacy", 0, []

    # Free users (and anonymous) always use spaCy.
    if tier != "registered":
        return await _spacy_result(text, language)

    # Registered users: truncate, then try premium under caps.
    max_chars = int(cfg.get("max_chars", 5000))
    snippet = text[:max_chars]

    # 1. Google NL — monthly UNIT cap (units = ceil(chars/1000), rounded up/request).
    if _google.configured():
        units = math.ceil(len(snippet) / 1000)
        unit_cap = int(cfg.get("google_nl_units_month", 5000))
        if await incr_by_capped(f"nl_units:{month_key()}", units, unit_cap):
            try:
                return "google_nl", units, await _google.extract(snippet, language)
            except ProviderError:
                pass  # fall through to next option

    # 2. LangExtract — daily REQUEST cap.
    if _langextract.configured():
        daily_cap = int(cfg.get("langextract_daily", 50))
        if await incr_capped(f"langextract:{day_key()}", daily_cap):
            try:
                return "langextract", 0, await _langextract.extract(snippet, language)
            except ProviderError:
                pass

    # 3. Fallback — spaCy (free, always available).
    return await _spacy_result(text, language)
