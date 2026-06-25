"""Application configuration and tier limits, loaded from env + limits.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core infra
    database_url: str = "postgresql+asyncpg://serp:serp@localhost:5432/serp"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    admin_bootstrap_email: str = "samuel.ohiri1@gmail.com"
    admin_bootstrap_password: str = "change-me"
    invite_expire_hours: int = 72

    # Frontend origin (CORS)
    frontend_origin: str = "http://localhost:3000"

    # Primary search providers
    brave_api_key: str = ""
    apify_api_token: str = ""

    # Entity extraction
    google_nl_api_key: str = ""
    langextract_llm_provider: str = "gemini"
    langextract_llm_key: str = ""
    langextract_model: str = "gemini-2.5-flash"

    # Fallback SERP vendors
    serper_api_key: str = ""
    scaleserp_api_key: str = ""
    serpapi_api_key: str = ""

    # Extraction
    extract_concurrency: int = 5
    extract_timeout_ms: int = 20000

    # Cache
    cache_ttl_seconds: int = 60 * 60 * 6  # 6 hours

    limits_path: str = "limits.yaml"

    @property
    def limits(self) -> dict:
        path = Path(self.limits_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / self.limits_path
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
