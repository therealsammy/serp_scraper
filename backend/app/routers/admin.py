"""Admin-only endpoints: users, invites, usage, provider health, costs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db, redis_client
from ..deps import require_admin
from ..models import Invite, Role, User
from ..providers import FALLBACK
from ..schemas import (
    CostStatus,
    InviteCreateRequest,
    InviteResponse,
    InviteRow,
    ProviderHealth,
    UserRow,
)
from ..services import cache
from ..services.quota import day_key, month_key
from ..services.security import new_invite_token

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---- Users ----
@router.get("/users", response_model=list[UserRow])
async def list_users(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).order_by(User.created_at.desc()))
    return [
        UserRow(id=u.id, email=u.email, role=u.role.value, tier=u.tier,
                is_active=u.is_active, created_at=u.created_at)
        for u in res.scalars()
    ]


@router.post("/users/{user_id}/disable")
async def disable_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = False
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/enable")
async def enable_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = True
    await db.commit()
    return {"ok": True}


# ---- Invites ----
@router.post("/invites", response_model=InviteResponse)
async def create_invite(
    body: InviteCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    raw, token_hash = new_invite_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.invite_expire_hours)
    invite = Invite(
        email=body.email, token_hash=token_hash, role=Role.user,
        tier=body.tier, expires_at=expires, created_by=admin.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    # The raw token is shown ONCE here so you can email the link yourself.
    accept_url = f"{settings.frontend_origin}/accept-invite?token={raw}"
    return InviteResponse(id=invite.id, email=invite.email,
                          accept_url=accept_url, expires_at=invite.expires_at)


@router.get("/invites", response_model=list[InviteRow])
async def list_invites(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invite).order_by(Invite.created_at.desc()))
    now = datetime.now(timezone.utc)
    rows: list[InviteRow] = []
    for inv in res.scalars():
        if inv.used_at is not None:
            status = "used"
        elif inv.expires_at.replace(tzinfo=timezone.utc) < now:
            status = "expired"
        else:
            status = "pending"
        rows.append(InviteRow(id=inv.id, email=inv.email, expires_at=inv.expires_at,
                              used_at=inv.used_at, status=status))
    return rows


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, db: AsyncSession = Depends(get_db)):
    inv = await db.get(Invite, invite_id)
    if not inv:
        raise HTTPException(404, "Invite not found")
    await db.delete(inv)  # revoke = delete the row, link dies instantly
    await db.commit()
    return {"ok": True}


# ---- Provider health (SERP fallback rotation) ----
@router.get("/providers", response_model=list[ProviderHealth])
async def provider_health():
    caps = settings.limits.get("fallback", {})
    out: list[ProviderHealth] = []
    for v in FALLBACK.vendors:
        used = int(await redis_client.get(f"serp:{v.name}:{day_key()}") or 0)
        breaker = await redis_client.exists(f"breaker:{v.name}") == 1
        cap = caps.get(v.name)
        out.append(ProviderHealth(
            name=v.name, daily_used=used, daily_cap=cap,
            healthy=v.configured() and not breaker, breaker_open=breaker,
        ))
    return out


# ---- Costs + kill-switch ----
@router.get("/costs", response_model=CostStatus)
async def costs():
    g = settings.limits.get("global", {})
    provider = g.get("guarded_provider", "apify")
    cap = int(g.get("daily_cap", 0))
    used = int(await redis_client.get(f"killswitch:{provider}:{day_key()}") or 0)
    return CostStatus(guarded_provider=provider, daily_used=used,
                      daily_cap=cap, kill_switch_active=used >= cap)


@router.get("/cache")
async def cache_stats():
    return await cache.stats()


@router.get("/entity-costs")
async def entity_costs():
    """Premium entity engine usage + estimated spend ($0 while under free tier)."""
    cfg = settings.limits.get("entities", {})
    unit_cap = int(cfg.get("google_nl_units_month", 5000))
    units = int(await redis_client.get(f"nl_units:{month_key()}") or 0)
    lx_cap = int(cfg.get("langextract_daily", 50))
    lx_used = int(await redis_client.get(f"langextract:{day_key()}") or 0)
    # Google NL: first 5k units/month free, then $0.001/unit.
    billable = max(units - 5000, 0)
    est_spend = round(billable * 0.001, 2)
    return {
        "google_nl_units_used": units,
        "google_nl_units_cap": unit_cap,
        "google_nl_free_tier": 5000,
        "google_nl_estimated_spend_usd": est_spend,
        "langextract_used_today": lx_used,
        "langextract_daily_cap": lx_cap,
    }
