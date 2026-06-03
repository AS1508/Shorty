from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SNOWFLAKE_NODE_ID_MAX = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://shorty:shorty@localhost:5432/shorty",
        description="SQLAlchemy async URL for the application database.",
    )
    short_base_url: str = Field(
        default="http://localhost:8000",
        description="Public base URL prepended to generated short codes.",
    )
    snowflake_node_id: int = Field(
        default=0,
        ge=0,
        lt=SNOWFLAKE_NODE_ID_MAX,
        description="Worker ID embedded in generated Snowflake IDs (0..1023).",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for the cache layer.",
    )

    @field_validator("short_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


def get_settings() -> Settings:
    return Settings()
