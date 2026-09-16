"""Load local configuration without connecting to external services."""

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
    # Only the explicit validation command may use these server-side settings.
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
