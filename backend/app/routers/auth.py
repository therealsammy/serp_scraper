"""Login + invite acceptance. NO public registration route exists by design."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Invite, User
from ..schemas import AcceptInviteRequest, LoginRequest, TokenResponse
from ..services.security import (
    create_access_token,
    hash_invite_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Generic message — never reveal whether token was bad / used / expired.
INVALID_INVITE = "Invalid or expired invitation"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == body.email))
    user = res.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(user.id, user.role.value, user.email)
    return TokenResponse(access_token=token, role=user.role.value, email=user.email)


@router.post("/accept-invite", response_model=TokenResponse)
async def accept_invite(body: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_invite_token(body.token)
    res = await db.execute(select(Invite).where(Invite.token_hash == token_hash))
    invite = res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if (
        invite is None
        or invite.used_at is not None
        or invite.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_INVITE)

    # Email is bound to the token; user cannot change it.
    existing = await db.execute(select(User).where(User.email == invite.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_INVITE)

    user = User(
        email=invite.email,
        password_hash=hash_password(body.password),
        role=invite.role,
        tier=invite.tier,
    )
    invite.used_at = now  # single-use: burn it
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role.value, user.email)
    return TokenResponse(access_token=token, role=user.role.value, email=user.email)


@router.get("/invite-info")
async def invite_info(token: str, db: AsyncSession = Depends(get_db)):
    """Lets the accept-invite page show the bound email (read-only)."""
    res = await db.execute(
        select(Invite).where(Invite.token_hash == hash_invite_token(token))
    )
    invite = res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        invite is None
        or invite.used_at is not None
        or invite.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_INVITE)
    return {"email": invite.email}
