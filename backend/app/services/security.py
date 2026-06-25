"""Password hashing, JWT, and invite-token helpers."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def create_access_token(sub: str, role: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": sub, "role": role, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ---- invite tokens: raw token shown once, only its hash is stored ----
def new_invite_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). Store only the hash."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_invite_token(raw)


def hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
