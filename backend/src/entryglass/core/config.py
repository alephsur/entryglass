"""Load local configuration without connecting to external services."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-side settings. Run commands from the repository root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ENTRYGLASS_",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    database_path: Path = Path("data/entryglass.sqlite3")
    nansen_timeout_seconds: float = Field(default=20.0, gt=0)
    nansen_max_concurrency: int = Field(default=1, ge=1, le=4)
    review_max_entries: int = Field(default=5, ge=1, le=30)
    review_max_requests: int = Field(default=15, ge=1, le=100)
    review_max_credits: int = Field(default=32, ge=1, le=500)
    # Only explicit server-side provider commands may use these settings.
    nansen_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="NANSEN_API_KEY",
        exclude=True,
        repr=False,
    )
    nansen_base_url: AnyHttpUrl = Field(
        default="https://api.nansen.ai",
        validation_alias="NANSEN_BASE_URL",
    )
