from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite+aiosqlite:///{(ROOT / 'refundrx.db').as_posix()}"
    groq_api_key: str | None = None
    # "auto" uses Groq when a key is set, otherwise the offline reference planner.
    planner_backend: str = "auto"
    # "qdrant" = bge-small-en-v1.5 embeddings in Qdrant local mode; "keyword" = no-download fallback.
    rag_backend: str = "qdrant"
    api_basic_auth_user: str | None = None
    api_basic_auth_password: str | None = None
    rate_limit_per_minute: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_model_pin() -> dict:
    with open(ROOT / "config" / "model_pin.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
