from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "LIVE Pulse AO Intelligence"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://live:live@localhost:5432/livepulse"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    seed_admin_password: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    openai_reasoning_effort: str = "medium"
    openai_text_verbosity: str = "medium"
    openai_verify_ssl: bool = True
    embedding_model: str = "text-embedding-3-small"
    storage_backend: str = "local"
    local_storage_path: Path = Path("storage")
    boamp_api_base_url: str = Field(
        default="https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
    )
    ted_api_base_url: str = "https://api.ted.europa.eu/v3/notices/search"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
