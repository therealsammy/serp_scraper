"""Search + extraction routes.

Flow:
  POST /search   -> authorize via quota engine, run provider (cache/own/pool/fallback),
                    store the result list under a job id, return the job id.
  GET  /stream   -> SSE: extract each URL with Playwright+trafilatura, push as ready.
  POST /export   -> CSV / JSON download.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse

from ..db import redis_client
from ..deps import optional_user
from ..models import User
from ..providers import FALLBACK, PRIMARY
from ..providers.base import ProviderError
from ..schemas import (
    ExportRequest,
    SearchJob,
    SearchRequest,
    SearchResult,
)
from ..services import cache
from ..services.export import to_csv, to_json
from ..services.extract import extract_stream
from ..services.identity import anonymous_identity
from ..services.quota import QuotaDenied, try_spend

router = APIRouter(tags=["search"])

JOB_TTL = 60 * 30  # results stay retrievable for 30 min


@router.post("/search", response_model=SearchJob)
async def search(
    body: SearchRequest,
    request: Request,
    response: Response,
    user: User | None = Depends(optional_user),
):
    provider_name = body.provider.lower()
    if provider_name not in PRIMARY:
        raise HTTPException(400, f"Unknown provider '{provider_name}'")
    count = max(1, min(body.count, 20))
    geo = body.geo
    # Geo-tagged cache key so e.g. London vs. Austin results don't collide.
    cache_q = f"{body.query}|{geo.country}|{geo.language}|{geo.location or ''}"

    # Identity + tier
    if user:
        identity, tier = f"user:{user.id}", user.tier
    else:
        identity, _ip, _fp = anonymous_identity(request, response)
        tier = "anonymous"

    # 1. Cache (spends nothing)
    cached = await cache.get(provider_name, cache_q, count)
    if cached is not None:
        job_id = await _store_job(cached)
        return SearchJob(job_id=job_id, query=body.query, provider=provider_name,
                         count=count, served_by=f"{provider_name}+cache", cached=True)

    # 2/3. Quota: own -> pool. On denial, try the SERP fallback rotation.
    served_by = provider_name
    results: list[SearchResult]
    try:
        how = await try_spend(identity=identity, tier=tier, provider=provider_name)
        served_by = f"{provider_name}:{how}"
        results = await PRIMARY[provider_name].search(body.query, count, geo)
    except QuotaDenied as denied:
        # 4. Fallback rotation (registered users only; anonymous get the wall).
        if tier != "registered" or not FALLBACK.configured():
            raise HTTPException(429, _grace_message(denied.reason))
        try:
            results = await FALLBACK.search(body.query, count, geo)
            served_by = "serp_fallback"
        except ProviderError:
            raise HTTPException(429, _grace_message("all_providers_exhausted"))
    except ProviderError as exc:
        raise HTTPException(502, str(exc))

    # Only cache non-empty result sets — never poison the cache with a failed/empty run.
    if results:
        await cache.put(provider_name, cache_q, count, results)
    job_id = await _store_job(results)
    return SearchJob(job_id=job_id, query=body.query, provider=provider_name,
                     count=count, served_by=served_by, cached=False)


@router.get("/stream/{job_id}")
async def stream(job_id: str):
    raw = await redis_client.get(f"job:{job_id}")
    if raw is None:
        raise HTTPException(404, "Job not found or expired")
    results = [SearchResult(**r) for r in json.loads(raw)]

    async def event_gen():
        yield _sse({"event": "start", "total": len(results)})
        async for extracted in extract_stream(results):
            yield _sse({"event": "result", "data": extracted.model_dump(mode="json")})
        yield _sse({"event": "done"})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/export")
async def export(body: ExportRequest):
    if body.format == "csv":
        return PlainTextResponse(
            to_csv(body.results),
            headers={"Content-Disposition": "attachment; filename=results.csv"},
            media_type="text/csv",
        )
    return PlainTextResponse(
        to_json(body.results),
        headers={"Content-Disposition": "attachment; filename=results.json"},
        media_type="application/json",
    )


@router.get("/usage")
async def usage(
    request: Request,
    response: Response,
    user: User | None = Depends(optional_user),
):
    from ..services.quota import usage_snapshot

    if user:
        return {"tier": user.tier, "providers": await usage_snapshot(f"user:{user.id}", user.tier)}
    identity, _ip, _fp = anonymous_identity(request, response)
    return {"tier": "anonymous", "providers": await usage_snapshot(identity, "anonymous")}


# ---- helpers ----
async def _store_job(results: list[SearchResult]) -> str:
    job_id = str(uuid.uuid4())
    payload = json.dumps([r.model_dump() for r in results])
    await redis_client.set(f"job:{job_id}", payload, ex=JOB_TTL)
    return job_id


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _grace_message(reason: str) -> str:
    return {
        "global_free_tier_exhausted": "Daily free-tier limit reached. Resets at 00:00 UTC.",
        "quota_exhausted": "You've used your searches for today. Resets at 00:00 UTC.",
        "all_providers_exhausted": "All search providers are temporarily exhausted. Try later.",
    }.get(reason, "Quota reached. Resets at 00:00 UTC.")
