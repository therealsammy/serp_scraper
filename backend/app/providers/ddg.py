"""DuckDuckGo provider via the HTML endpoint (no key, no flaky deps).

We hit html.duckduckgo.com directly with httpx and parse results with lxml
(already available via trafilatura). This avoids the `ddgs` package's bundled
TLS-impersonation client, which is brittle across environments.
"""
from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import httpx
from lxml import html as lxml_html

from ..config import settings
from ..schemas import GeoOptions, SearchResult
from .base import ProviderError

ENDPOINT = "https://html.duckduckgo.com/html/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
}


def _clean_href(href: str) -> str:
    # DDG wraps links as //duckduckgo.com/l/?uddg=<encoded-target>
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    return href


class DuckDuckGoProvider:
    name = "ddg"

    def configured(self) -> bool:
        return True  # no credentials needed

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        # DDG HTML endpoint doesn't take structured geo; ignored here.
        # Optional proxy (e.g. Webshare rotating endpoint) dodges datacenter-IP
        # challenges. httpx 0.27 takes a single `proxy=` string.
        client_kwargs: dict = {"timeout": 15, "headers": HEADERS, "follow_redirects": True}
        if settings.ddg_proxy:
            client_kwargs["proxy"] = settings.ddg_proxy
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.post(ENDPOINT, data={"q": query})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"DuckDuckGo request failed: {exc}") from exc

        # Detect an anti-bot challenge page (common from datacenter IPs — covers both
        # DDG's own "anomaly modal" image CAPTCHA and Cloudflare-style interstitials).
        # The parser would otherwise find no results and return an empty list.
        low = resp.text.lower()
        if ("anomaly-modal" in low or "challenge-submit" in low
                or "challenge-form" in low or "verifying your browser" in low
                or "challenge-platform" in low or "/cdn-cgi/challenge" in low):
            raise ProviderError(
                "DuckDuckGo issued a bot challenge from this server. "
                "Try Google — DDG needs a residential proxy to work from a datacenter."
            )

        tree = lxml_html.fromstring(resp.text)
        results: list[SearchResult] = []
        for node in tree.xpath('//div[contains(@class, "result__body")]'):
            links = node.xpath('.//a[contains(@class, "result__a")]')
            if not links:
                continue
            link = links[0]
            href = _clean_href(link.get("href", ""))
            if not href.startswith("http"):
                continue
            snippet_nodes = node.xpath('.//a[contains(@class, "result__snippet")]')
            snippet = snippet_nodes[0].text_content().strip() if snippet_nodes else ""
            results.append(
                SearchResult(
                    title=link.text_content().strip(),
                    url=href,
                    snippet=snippet,
                    rank=len(results) + 1,
                    source_provider=self.name,
                )
            )
            if len(results) >= count:
                break
        return results
