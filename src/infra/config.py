from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SNOWFLAKE_NODE_ID_MAX = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="mysql+aiomysql://shorty:shorty@localhost:3306/shorty",
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
    proxy_shared_secret: str = Field(
        default="",
        description="Shared HMAC secret for verifying X-Auth-Signature from the proxy.",
    )
    rate_limit_create_count: int = Field(
        default=20,
        ge=1,
        description="Max URLs a single authenticated user can create per window.",
    )
    rate_limit_create_window_seconds: int = Field(
        default=3600,
        ge=1,
        description="Duration in seconds of the creation rate limit window (default 1 hour).",
    )
    rate_limit_redirect_count: int = Field(
        default=100,
        ge=1,
        description="Max redirect requests per IP per window.",
    )
    rate_limit_redirect_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Duration in seconds of the redirect rate limit window (default 1 minute).",
    )
    rate_limit_my_urls_count: int = Field(
        default=60,
        ge=1,
        description="Max requests per user per window on /my-urls endpoints.",
    )
    rate_limit_my_urls_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Duration in seconds of the /my-urls rate limit window (default 1 minute).",
    )

    admin_emails: frozenset[str] = Field(
        default_factory=frozenset,
        description="Comma-separated admin email addresses (empty = no admins).",
    )

    @field_validator("short_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _parse_admin_emails(cls, v: object) -> frozenset[str]:
        if isinstance(v, str):
            return frozenset(e.strip() for e in v.split(",") if e.strip())
        if isinstance(v, (list, set, frozenset)):
            return frozenset(str(e).strip() for e in v)
        return frozenset()


def get_settings() -> Settings:
    return Settings()
