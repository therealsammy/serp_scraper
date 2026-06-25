"""Provider interface + shared errors."""
from __future__ import annotations

from typing import Protocol

from ..schemas import GeoOptions, SearchResult


class ProviderError(Exception):
    """Generic provider failure (network / parse)."""


class QuotaExceeded(ProviderError):
    """Provider returned a 429 / quota signal."""


class ProviderUnavailable(ProviderError):
    """Provider not configured (missing key) or 5xx."""


class SearchProvider(Protocol):
    name: str

    def configured(self) -> bool:
        """Whether the provider has the credentials it needs."""
        ...

    async def search(
        self, query: str, count: int, geo: GeoOptions | None = None
    ) -> list[SearchResult]:
        ...
