"""Free local entity extraction with spaCy + a computed salience heuristic.

The spaCy model is loaded once at module level (lazy), mirroring the shared
Playwright browser singleton in services/extract.py. Salience is approximated as a
normalized blend of mention frequency, first-mention position, and title presence —
spaCy has no native salience score.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from ...schemas import EntityResult

_nlp = None
_nlp_lock = asyncio.Lock()

# Entity labels worth surfacing (skip dates, cardinals, percents, etc.).
_KEEP = {"PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "WORK_OF_ART",
         "FAC", "NORP", "LAW", "LANGUAGE"}


async def _get_nlp():
    global _nlp
    async with _nlp_lock:
        if _nlp is None:
            import spacy
            _nlp = await asyncio.to_thread(spacy.load, "en_core_web_sm")
    return _nlp


class SpacyProvider:
    name = "spacy"

    def configured(self) -> bool:
        return True

    async def extract(self, text: str, language: str, top_n: int = 10) -> list[EntityResult]:
        nlp = await _get_nlp()
        return await asyncio.to_thread(self._run, nlp, text, top_n)

    def _run(self, nlp, text: str, top_n: int) -> list[EntityResult]:
        doc = nlp(text)
        total = max(len(text), 1)
        title_zone = text[:200].lower()

        agg: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"mentions": 0, "first": total, "type": ""}
        )
        for ent in doc.ents:
            if ent.label_ not in _KEEP:
                continue
            key = (ent.text.strip(), ent.label_)
            if not key[0]:
                continue
            a = agg[key]
            a["mentions"] += 1
            a["first"] = min(a["first"], ent.start_char)
            a["type"] = ent.label_

        if not agg:
            return []

        max_mentions = max(a["mentions"] for a in agg.values())
        scored: list[EntityResult] = []
        for (name, _label), a in agg.items():
            freq = a["mentions"] / max_mentions
            position = 1.0 - (a["first"] / total)          # earlier = higher
            title_bonus = 0.25 if name.lower() in title_zone else 0.0
            raw = 0.55 * freq + 0.45 * position + title_bonus
            scored.append(EntityResult(
                name=name, type=a["type"], salience=raw,
                mentions=a["mentions"], source="spacy",
            ))

        # Normalize salience to 0..1 across the returned set.
        top = sorted(scored, key=lambda e: e.salience, reverse=True)[:top_n]
        peak = max((e.salience for e in top), default=1.0) or 1.0
        for e in top:
            e.salience = round(e.salience / peak, 4)
        return top
