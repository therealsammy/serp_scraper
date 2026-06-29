"""Content extraction: Playwright fetches each page, trafilatura cleans it.

A single shared browser is launched lazily and reused. Per-URL extraction runs
concurrently behind a semaphore and yields results as they complete (for SSE).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

import trafilatura

from ..config import settings
from ..schemas import ExtractedResult, SearchResult

_browser = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    global _browser
    async with _browser_lock:
        if _browser is None:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            _browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    # Critical in containers: /dev/shm is tiny (~64MB), so Chromium
                    # must use /tmp instead or concurrent tabs crash (OOM) → "error".
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
    return _browser


async def shutdown_browser() -> None:
    global _browser
    if _browser is not None:
        await _browser.close()
        _browser = None


async def _fetch_html(url: str) -> str | None:
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    )
    try:
        page = await context.new_page()
        # Block heavy resources we don't need (we only parse HTML text). Cuts memory
        # and bandwidth sharply — the biggest lever for stability on small instances.
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font", "stylesheet"}
            else route.continue_(),
        )
        await page.goto(url, timeout=settings.extract_timeout_ms, wait_until="domcontentloaded")
        return await page.content()
    finally:
        await context.close()


async def _fetch_html_retry(url: str, attempts: int = 2) -> str | None:
    """Fetch with one retry — recovers transient failures (cold pages, blips)."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await _fetch_html(url)
        except Exception as exc:  # noqa: BLE001 — retry any fetch failure
            last_exc = exc
            if i < attempts - 1:
                await asyncio.sleep(0.5)
    if last_exc:
        raise last_exc
    return None


async def extract_one(result: SearchResult) -> ExtractedResult:
    out = ExtractedResult(**result.model_dump())
    out.domain = urlparse(result.url).netloc
    try:
        html = await _fetch_html_retry(result.url)
        if not html:
            out.status = "blocked"
            return out
        text = trafilatura.extract(
            html, include_comments=False, include_tables=False, favor_recall=True
        )
        if not text:
            out.status = "blocked"
            return out
        out.full_text = text
        out.word_count = len(text.split())
        out.status = "extracted"
        out.extracted_at = datetime.now(timezone.utc)
    except Exception:
        out.status = "error"
    return out


async def extract_stream(results: list[SearchResult]):
    """Yield ExtractedResult objects as each completes (order = completion order)."""
    sem = asyncio.Semaphore(settings.extract_concurrency)

    async def _guarded(r: SearchResult) -> ExtractedResult:
        async with sem:
            return await extract_one(r)

    tasks = [asyncio.create_task(_guarded(r)) for r in results]
    for coro in asyncio.as_completed(tasks):
        yield await coro
