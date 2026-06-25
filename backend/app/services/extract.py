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
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
        await page.goto(url, timeout=settings.extract_timeout_ms, wait_until="domcontentloaded")
        return await page.content()
    finally:
        await context.close()


async def extract_one(result: SearchResult) -> ExtractedResult:
    out = ExtractedResult(**result.model_dump())
    out.domain = urlparse(result.url).netloc
    try:
        html = await _fetch_html(result.url)
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
