"""Application configuration management using Pydantic settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core settings
    database_url: str = Field(..., alias="DATABASE_URL")
    blob_storage_path: Path = Field(..., alias="BLOB_STORAGE_PATH")
    log_level: str = Field(..., alias="LOG_LEVEL")
    log_json_format: bool = Field(False, alias="LOG_JSON_FORMAT")

    # LLM Provider API Keys
    ohmygpt_api_key: SecretStr = Field(..., alias="OHMYGPT_API_KEY")  # Claude Haiku 4.5
    megallm_api_key: SecretStr = Field(..., alias="MEGALLM_API_KEY")  # GPT-OSS-120b
    nebius_api_key: SecretStr = Field(..., alias="NEBIUS_API_KEY")  # GLM-4.5-Air
    deepinfra_api_key: SecretStr = Field(..., alias="DEEPINFRA_API_KEY")  # Qwen3-235B

    # Legacy keys (kept for embeddings - OpenAI text-embedding-3-small)
    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")

    @field_validator("database_url", "log_level", mode="before")
    @classmethod
    def strip_strings(cls, value: object, _: ValidationInfo) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL must not be empty")
        return value

    @field_validator("blob_storage_path", mode="before")
    @classmethod
    def validate_blob_storage_path(cls, value: Path | str) -> Path | str:
        if isinstance(value, str):
            if value.strip() == "":
                raise ValueError("BLOB_STORAGE_PATH must not be empty")
            return value.strip()

        if str(value).strip() == "":
            raise ValueError("BLOB_STORAGE_PATH must not be empty")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed_levels)}")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached instance of Settings loaded from the environment."""

    return Settings()  # type: ignore[call-arg]
