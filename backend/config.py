from pathlib import Path
from typing import Literal

from pydantic import PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = BACKEND_DIR.parent
# Keep this aligned with nodes.embedding. Changing it requires a schema migration.
SCHEMA_EMBEDDING_DIMENSIONS = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    DATABASE_URL: SecretStr = SecretStr(
        "postgresql+asyncpg://codescape@localhost:5432/codescape"
    )
    AI_PROVIDER: Literal["gemini", "ollama"] = "gemini"
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_REASONING_MODEL: str = "gemini-3.8-flash"
    GEMINI_REASONING_FALLBACK_MODEL: str | None = None
    GEMINI_SUMMARY_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSIONS: int = SCHEMA_EMBEDDING_DIMENSIONS
    REDIS_URL: SecretStr | None = None
    REPOS_STORAGE_PATH: Path = REPOSITORY_ROOT / "data" / "repos"
    EPHEMERAL_RUNS_PATH: Path = REPOSITORY_ROOT / "data" / "runs"
    SANDBOX_IMAGE_TAG: str = "codescape-sandbox:latest"
    SANDBOX_TIMEOUT_SECONDS: PositiveInt = 8
    DEMO_MODE: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from None
        if url.drivername != "postgresql+asyncpg" or not url.database:
            raise ValueError("DATABASE_URL must use postgresql+asyncpg and name a database")
        return value

    @field_validator("EMBEDDING_DIMENSIONS")
    @classmethod
    def validate_embedding_dimensions(cls, value: int) -> int:
        if value != SCHEMA_EMBEDDING_DIMENSIONS:
            raise ValueError(f"The PostgreSQL schema requires vector({SCHEMA_EMBEDDING_DIMENSIONS})")
        return value

    @field_validator("REPOS_STORAGE_PATH", "EPHEMERAL_RUNS_PATH")
    @classmethod
    def resolve_storage_path(cls, value: Path) -> Path:
        return (REPOSITORY_ROOT / value).resolve()
