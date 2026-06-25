"""The quota engine: precedence chain, atomic counters, borrow pool, kill-switch.

Precedence per request:
  1. cache hit            -> handled by the route before calling here
  2. user's own quota     -> spend if available
  3. shared anon pool     -> borrow if global free-tier kill-switch allows
  4. (caller falls back to the SERP rotation provider)
  5. else GraceExhausted
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from ..db import redis_client


def day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# --- atomic INCR-with-cap. Returns True if the increment was allowed. ---
_INCR_CAPPED_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local cap = tonumber(ARGV[1])
if cap >= 0 and current >= cap then
  return 0
end
local v = redis.call('INCR', KEYS[1])
if v == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 1
"""

# --- atomic borrow from the shared anonymous pool, gated by kill-switch. ---
# KEYS[1]=pool counter  KEYS[2]=killswitch counter
# ARGV[1]=pool cap  ARGV[2]=killswitch cap  ARGV[3]=ttl
_BORROW_LUA = """
local pool = tonumber(redis.call('GET', KEYS[1]) or '0')
local poolcap = tonumber(ARGV[1])
if pool >= poolcap then return 0 end
local kcap = tonumber(ARGV[2])
if kcap >= 0 then
  local kused = tonumber(redis.call('GET', KEYS[2]) or '0')
  if kused >= kcap then return -1 end   -- kill-switch tripped
  local kv = redis.call('INCR', KEYS[2])
  if kv == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]) end
end
local v = redis.call('INCR', KEYS[1])
if v == 1 then redis.call('EXPIRE', KEYS[1], ARGV[3]) end
return 1
"""

# --- atomic add-N-with-cap. Adds `amount` only if it stays within `cap`. ---
# Returns 1 if the whole amount was added, 0 if it would exceed the cap.
_INCR_BY_CAPPED_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local cap = tonumber(ARGV[1])
local amount = tonumber(ARGV[2])
if cap >= 0 and current + amount > cap then
  return 0
end
local v = redis.call('INCRBY', KEYS[1], amount)
if v == amount then
  redis.call('EXPIRE', KEYS[1], ARGV[3])
end
return 1
"""

_DAY_TTL = 60 * 60 * 26  # a bit over a day so the window fully rolls
_MONTH_TTL = 60 * 60 * 24 * 32  # a bit over a month so the window fully rolls


class QuotaDenied(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def incr_capped(key: str, cap: int, ttl: int = _DAY_TTL) -> bool:
    """Generic atomic capped increment. cap < 0 means unlimited."""
    res = await redis_client.eval(_INCR_CAPPED_LUA, 1, key, str(cap), str(ttl))
    return bool(res)


async def incr_by_capped(key: str, amount: int, cap: int, ttl: int = _MONTH_TTL) -> bool:
    """Atomically add `amount` only if it stays within `cap`. cap < 0 = unlimited.
    Returns True if added, False if it would exceed the cap."""
    res = await redis_client.eval(
        _INCR_BY_CAPPED_LUA, 1, key, str(cap), str(amount), str(ttl)
    )
    return bool(res)


def month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _cap_for(tier: str, provider: str) -> int:
    limits = settings.limits.get(tier, {})
    val = limits.get(provider, 0)
    if isinstance(val, str) and val.lower() == "unlimited":
        return -1
    return int(val)


def _guarded() -> tuple[str | None, int]:
    """The provider protected by the global daily kill-switch, and its cap."""
    g = settings.limits.get("global", {})
    return g.get("guarded_provider"), int(g.get("daily_cap", 0))


async def _killswitch_state(provider: str) -> tuple[int, int, bool]:
    """For the guarded provider: (used, cap, tripped). Others: (0, -1, False)."""
    guarded, cap = _guarded()
    if provider != guarded:
        return 0, -1, False
    used = int(await redis_client.get(f"killswitch:{provider}:{day_key()}") or 0)
    return used, cap, used >= cap


async def try_spend(
    *, identity: str, tier: str, provider: str
) -> str:
    """Attempt to authorize one search. Returns how it was satisfied:
    'own' | 'pool' | raises QuotaDenied (caller then tries SERP fallback)."""

    # Kill-switch first — never spend past the free ceiling on a billable provider.
    used, kcap, tripped = await _killswitch_state(provider)
    if tripped:
        raise QuotaDenied("global_free_tier_exhausted")

    # 2. User's own quota.
    own_cap = _cap_for(tier, provider)
    own_key = f"quota:{identity}:{provider}:{day_key()}"
    if own_cap < 0:  # unlimited
        await redis_client.incr(own_key)
        await _count_killswitch(provider)
        return "own"
    if await incr_capped(own_key, own_cap):
        await _count_killswitch(provider)
        return "own"

    # 3. Borrow from the shared anonymous pool (registered users only),
    #    gated by the global kill-switch counter (atomic).
    if tier == "registered":
        anon_cap = _cap_for("anonymous", provider)
        pool_key = f"pool:anon:{provider}:{day_key()}"
        ks_key = f"killswitch:{provider}:{day_key()}"
        res = await redis_client.eval(
            _BORROW_LUA, 2, pool_key, ks_key,
            str(anon_cap), str(kcap), str(_DAY_TTL),
        )
        if res == 1:
            return "pool"
        if res == -1:
            raise QuotaDenied("global_free_tier_exhausted")

    raise QuotaDenied("quota_exhausted")


async def _count_killswitch(provider: str) -> None:
    """Increment the global daily counter for the guarded (billable) provider."""
    guarded, _ = _guarded()
    if provider == guarded:
        key = f"killswitch:{provider}:{day_key()}"
        v = await redis_client.incr(key)
        if v == 1:
            await redis_client.expire(key, _DAY_TTL)


async def usage_snapshot(identity: str, tier: str) -> dict[str, dict]:
    """For UI: per-provider used/cap for this identity."""
    out: dict[str, dict] = {}
    providers = list(settings.limits.get(tier, settings.limits.get("registered", {})).keys())
    for provider in providers:
        cap = _cap_for(tier, provider)
        used = int(await redis_client.get(f"quota:{identity}:{provider}:{day_key()}") or 0)
        out[provider] = {
            "used": used,
            "cap": None if cap < 0 else cap,
            "remaining": None if cap < 0 else max(cap - used, 0),
        }
    return out
