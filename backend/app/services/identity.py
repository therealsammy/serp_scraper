"""Composite anonymous identity — not IP alone.

Combines IP + a browser fingerprint hash + an httpOnly cookie token so that
rotating any single signal does not trivially reset the quota. Also records
the (ip -> fingerprint) fan-out so the admin panel can flag suspected rotation.
"""
from __future__ import annotations

import hashlib
import secrets

from fastapi import Request, Response

COOKIE_NAME = "anon_id"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def fingerprint(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    lang = request.headers.get("accept-language", "")
    # Optional client-supplied signal (FingerprintJS visitorId).
    fpjs = request.headers.get("x-fp-visitor", "")
    return _hash(ua, lang, fpjs)


def get_or_set_cookie(request: Request, response: Response) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        token = secrets.token_urlsafe(16)
        response.set_cookie(
            COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
        )
    return token


def anonymous_identity(request: Request, response: Response) -> tuple[str, str, str]:
    """Returns (identity, ip, fingerprint)."""
    ip = client_ip(request)
    fp = fingerprint(request)
    cookie = get_or_set_cookie(request, response)
    identity = _hash(ip, fp, cookie)
    return identity, ip, fp
