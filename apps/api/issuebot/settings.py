"""Process configuration. Secrets come from the environment or an untracked .env file."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def discover_env_file() -> str | None:
    if os.environ.get("ISSUEBOT_IGNORE_ENV_FILE") == "1":
        return None
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ISSUEBOT_",
        env_file=discover_env_file(),
        extra="ignore",
    )

    env: str = "development"
    database_url: str = "postgresql+psycopg://issuebot:change-me@localhost:5432/issuebot"
    public_base_url: str = "http://localhost:8080"
    admin_username: str = "admin"
    admin_password: str | None = None
    fernet_key: str | None = None
    docsgpt_base_url: str = ""
    docsgpt_api_key: str = ""
    docsgpt_agent_id: str = ""
    github_app_id: str = ""
    github_private_key: str = ""
    github_private_key_path: str = ""
    github_webhook_secret: str = ""
    allowed_repos: str = ""
    max_issue_chars: int = Field(default=12000, ge=500, le=100_000)
    job_max_attempts: int = Field(default=5, ge=1, le=20)
    manual_retry_limit: int = Field(default=3, ge=0, le=20)
    http_connect_timeout: float = Field(default=5.0, gt=0, le=60)
    http_read_timeout: float = Field(default=60.0, gt=0, le=300)
    http_retries: int = Field(default=2, ge=0, le=5)
    log_level: str = "INFO"
    demo_mode: bool = False
    worker_enabled: bool = True
    allow_private_docsgpt: bool = False
    publish_enabled: bool = False

    @field_validator("env")
    @classmethod
    def _env(cls, value: str) -> str:
        if value not in {"development", "production"}:
            raise ValueError("ISSUEBOT_ENV must be development or production")
        return value

    @field_validator("public_base_url")
    @classmethod
    def _public_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise ValueError("ISSUEBOT_PUBLIC_BASE_URL must be an absolute http(s) URL")
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def _level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError("ISSUEBOT_LOG_LEVEL is invalid")
        return upper

    @property
    def production(self) -> bool:
        return self.env == "production"


def get_settings() -> Settings:
    return Settings()
