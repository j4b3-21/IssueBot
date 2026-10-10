"""Relational schema. Statuses are strings so the migration stays portable."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    docsgpt_base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    docsgpt_agent_id: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    docsgpt_api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_app_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    github_private_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_webhook_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_repos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    publish_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GithubInstallation(Base):
    __tablename__ = "github_installations"

    installation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_login: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    ignore_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repo_full_name: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    issue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    issue_title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    issue_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    issue_author: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    issue_labels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manual_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvestigationJob(Base):
    __tablename__ = "investigation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("investigations.id"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PublishedComment(Base):
    __tablename__ = "published_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("investigations.id"), unique=True, nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
