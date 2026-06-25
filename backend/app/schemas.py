"""Pydantic request/response schemas (mirror into TS on the frontend)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


# ---- Search / extraction ----
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    rank: int
    source_provider: str


class ExtractedResult(SearchResult):
    full_text: str = ""
    word_count: int = 0
    domain: str = ""
    status: str = "pending"  # extracted | blocked | error | pending
    extracted_at: datetime | None = None


class GeoOptions(BaseModel):
    country: str = "us"          # ISO-2, e.g. us, gb, de
    language: str = "en"         # result language, e.g. en, fr, zh-CN
    location: str | None = None  # plain city string, e.g. "Austin, Texas, United States"


class SearchRequest(BaseModel):
    query: str
    provider: str = "ddg"  # apify | brave | ddg
    count: int = 10
    geo: GeoOptions = GeoOptions()


class SearchJob(BaseModel):
    job_id: str
    query: str
    provider: str
    count: int
    served_by: str  # which provider actually answered (after fallback)
    cached: bool = False


class ExportRequest(BaseModel):
    results: list[ExtractedResult]
    format: str = "json"  # json | csv


# ---- Entity extraction ----
class EntityResult(BaseModel):
    name: str
    type: str = ""           # PERSON, ORG, LOCATION, etc.
    salience: float = 0.0    # 0..1, higher = more central to the text
    mentions: int = 1
    source: str = "spacy"    # google_nl | langextract | spacy


class EntityRequest(BaseModel):
    text: str
    language: str = "en"


class EntityResponse(BaseModel):
    source: str
    units_charged: int = 0   # Google NL billing units consumed (0 for spaCy)
    entities: list[EntityResult]


# ---- Auth / invites ----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: EmailStr


class AcceptInviteRequest(BaseModel):
    token: str
    password: str


class InviteCreateRequest(BaseModel):
    email: EmailStr
    tier: str = "registered"


class InviteResponse(BaseModel):
    id: str
    email: EmailStr
    accept_url: str
    expires_at: datetime


class InviteRow(BaseModel):
    id: str
    email: EmailStr
    expires_at: datetime
    used_at: datetime | None
    status: str  # pending | used | expired


class UserRow(BaseModel):
    id: str
    email: EmailStr
    role: str
    tier: str
    is_active: bool
    created_at: datetime


# ---- Admin dashboards ----
class ProviderHealth(BaseModel):
    name: str
    daily_used: int
    daily_cap: int | None
    healthy: bool
    breaker_open: bool


class CostStatus(BaseModel):
    guarded_provider: str
    daily_used: int
    daily_cap: int
    kill_switch_active: bool


class UsageRow(BaseModel):
    identity: str
    provider: str
    used: int
