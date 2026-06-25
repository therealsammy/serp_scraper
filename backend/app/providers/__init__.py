"""Search provider registry."""
from __future__ import annotations

from .apify import ApifyGoogleProvider
from .base import SearchProvider
from .brave import BraveProvider
from .ddg import DuckDuckGoProvider
from .fallback import SerpFallbackProvider

# Primary providers, keyed by the name the frontend sends.
PRIMARY: dict[str, SearchProvider] = {
    "apify": ApifyGoogleProvider(),   # real Google results via Apify's managed actor
    "brave": BraveProvider(),
    "ddg": DuckDuckGoProvider(),
}

FALLBACK = SerpFallbackProvider()

__all__ = ["PRIMARY", "FALLBACK", "SearchProvider"]
