"""Effective configuration: saved settings override environment values when present."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from issuebot.crypto import CryptoError, decrypt_secret
from issuebot.db import utcnow
from issuebot.models import AppSettings, User
from issuebot.safety import hash_password, parse_repo_list
from issuebot.settings import Settings


@dataclass
class RuntimeConfig:
    docsgpt_base_url: str
    docsgpt_api_key: str
    docsgpt_agent_id: str
    github_app_id: str
    github_private_key: str
    github_webhook_secret: str
    allowed_repos: list[str]
    publish_enabled: bool
    demo_mode: bool


def private_key_from_env(settings: Settings) -> str:
    if settings.github_private_key_path:
        path = Path(settings.github_private_key_path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return ""
    return settings.github_private_key.replace("\\n", "\n")


def _decrypt_or_blank(fernet_key: str | None, ciphertext: str | None, fallback: str) -> str:
    if not ciphertext:
        return fallback
    try:
        return decrypt_secret(fernet_key, ciphertext)
    except CryptoError:
        return ""


def load_runtime(session: Session, settings: Settings) -> RuntimeConfig:
    row = session.get(AppSettings, 1)
    repos: list[str]
    if row is not None and row.allowed_repos is not None:
        repos = [str(item) for item in row.allowed_repos]
    else:
        repos = parse_repo_list(settings.allowed_repos)
    if settings.demo_mode and not repos:
        repos = ["acme/widget"]
    publish = row.publish_enabled if row is not None else settings.publish_enabled
    return RuntimeConfig(
        docsgpt_base_url=(
            row.docsgpt_base_url if row and row.docsgpt_base_url else settings.docsgpt_base_url
        ).rstrip("/"),
        docsgpt_api_key=_decrypt_or_blank(
            settings.fernet_key,
            row.docsgpt_api_key_ciphertext if row else None,
            settings.docsgpt_api_key,
        ),
        docsgpt_agent_id=(
            row.docsgpt_agent_id if row and row.docsgpt_agent_id else settings.docsgpt_agent_id
        ),
        github_app_id=(row.github_app_id if row and row.github_app_id else settings.github_app_id),
        github_private_key=_decrypt_or_blank(
            settings.fernet_key,
            row.github_private_key_ciphertext if row else None,
            private_key_from_env(settings),
        ),
        github_webhook_secret=_decrypt_or_blank(
            settings.fernet_key,
            row.github_webhook_secret_ciphertext if row else None,
            settings.github_webhook_secret,
        ),
        allowed_repos=repos,
        publish_enabled=bool(publish) and not settings.demo_mode,
        demo_mode=settings.demo_mode,
    )


def bootstrap(session: Session, settings: Settings) -> None:
    if session.query(User).count() == 0:
        password = settings.admin_password or ""
        if len(password) < 12:
            raise RuntimeError(
                "ISSUEBOT_ADMIN_PASSWORD is required to create the first administrator "
                "and must be at least 12 characters."
            )
        session.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(password),
                failed_logins=0,
            )
        )
    if session.get(AppSettings, 1) is None:
        allowed = None
        if settings.demo_mode and not parse_repo_list(settings.allowed_repos):
            allowed = ["acme/widget"]
        session.add(
            AppSettings(
                id=1,
                docsgpt_base_url="",
                docsgpt_agent_id="",
                github_app_id="",
                allowed_repos=allowed,
                publish_enabled=settings.publish_enabled,
                updated_at=utcnow(),
            )
        )
    session.commit()
