"""Encode a plain location string into Google's UULE parameter.

Google's "canonical name" UULE (role 2) format is:
    w+CAIQICI + <length-char> + base64(location)
where <length-char> encodes the byte length of the location string via a fixed
64-character alphabet. This is the widely-used scheme for city-level geo-targeting.
"""
from __future__ import annotations

import base64

# Index = length of the location string; value = the corresponding marker char.
_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def encode_uule(location: str) -> str:
    location = location.strip()
    if not location:
        return ""
    b64 = base64.b64encode(location.encode("utf-8")).decode("ascii")
    length_char = _ALPHABET[len(location) % len(_ALPHABET)]
    return f"w+CAIQICI{length_char}{b64}"
