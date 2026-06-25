"""Per-result entity extraction. Tier decides the engine (see orchestrator)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import optional_user
from ..models import User
from ..providers.entities import extract_entities
from ..schemas import EntityRequest, EntityResponse

router = APIRouter(tags=["entities"])


@router.post("/entities", response_model=EntityResponse)
async def entities(body: EntityRequest, user: User | None = Depends(optional_user)):
    tier = user.tier if user else "anonymous"
    source, units, results = await extract_entities(body.text, body.language, tier)
    return EntityResponse(source=source, units_charged=units, entities=results)
