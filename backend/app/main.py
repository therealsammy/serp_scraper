"""FastAPI entrypoint: CORS, lifespan (DB init + seed admin), router wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .db import SessionLocal, init_db
from .models import Role, User
from .routers import admin, auth, entities, search
from .services.extract import shutdown_browser
from .services.security import hash_password


async def _seed_admin() -> None:
    """Create the bootstrap admin on first run (no public signup exists)."""
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.email == settings.admin_bootstrap_email))
        if res.scalar_one_or_none():
            return
        db.add(User(
            email=settings.admin_bootstrap_email,
            password_hash=hash_password(settings.admin_bootstrap_password),
            role=Role.admin,
            tier="registered",
        ))
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed_admin()
    yield
    await shutdown_browser()


app = FastAPI(title="SERP Research Tool", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(entities.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
