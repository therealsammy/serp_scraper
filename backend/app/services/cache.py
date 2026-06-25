"""Query result cache — a hit spends zero quota and stretches every free tier."""
from __future__ import annotations

import hashlib
import json

from ..config import settings
from ..db import redis_client
from ..schemas import SearchResult

HITS_KEY = "cache:stats:hits"
MISS_KEY = "cache:stats:miss"


def _key(provider: str, query: str, count: int) -> str:
    norm = query.strip().lower()
    digest = hashlib.sha256(f"{provider}:{norm}:{count}".encode()).hexdigest()[:24]
    return f"cache:{provider}:{digest}"


async def get(provider: str, query: str, count: int) -> list[SearchResult] | None:
    raw = await redis_client.get(_key(provider, query, count))
    if raw is None:
        await redis_client.incr(MISS_KEY)
        return None
    await redis_client.incr(HITS_KEY)
    return [SearchResult(**r) for r in json.loads(raw)]


async def put(provider: str, query: str, count: int, results: list[SearchResult]) -> None:
    payload = json.dumps([r.model_dump() for r in results])
    await redis_client.set(
        _key(provider, query, count), payload, ex=settings.cache_ttl_seconds
    )


async def stats() -> dict[str, int]:
    hits = int(await redis_client.get(HITS_KEY) or 0)
    miss = int(await redis_client.get(MISS_KEY) or 0)
    total = hits + miss
    return {"hits": hits, "misses": miss, "hit_rate_pct": round(100 * hits / total) if total else 0}
