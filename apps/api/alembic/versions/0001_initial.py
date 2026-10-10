"""Initial IssueBot schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("docsgpt_base_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("docsgpt_agent_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("docsgpt_api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("github_app_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("github_private_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("github_webhook_secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("allowed_repos", sa.JSON(), nullable=True),
        sa.Column("publish_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "github_installations",
        sa.Column("installation_id", sa.BigInteger(), primary_key=True),
        sa.Column("account_login", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("delivery_id", sa.String(80), primary_key=True),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("ignore_reason", sa.String(64), nullable=True),
    )
    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("delivery_id", sa.String(80), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=True),
        sa.Column("repo_full_name", sa.String(300), nullable=False),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("issue_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("issue_title", sa.String(500), nullable=False, server_default=""),
        sa.Column("issue_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("issue_author", sa.String(200), nullable=False, server_default=""),
        sa.Column("issue_labels", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("delivery_id"),
    )
    op.create_index("ix_investigations_repo", "investigations", ["repo_full_name"])
    op.create_index("ix_investigations_repo_issue", "investigations", ["repo_full_name", "issue_number"])
    op.create_index("ix_investigations_status", "investigations", ["status"])
    op.create_index("ix_investigations_created", "investigations", ["created_at"])
    op.create_table(
        "investigation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("investigation_id", sa.Uuid(), sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(64), nullable=True),
        sa.UniqueConstraint("investigation_id"),
    )
    op.create_index("ix_jobs_status_run_after", "investigation_jobs", ["status", "run_after"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "published_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("investigation_id", sa.Uuid(), sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("github_comment_id", sa.BigInteger(), nullable=True),
        sa.Column("comment_url", sa.String(500), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("investigation_id"),
    )


def downgrade() -> None:
    op.drop_table("published_comments")
    op.drop_table("audit_events")
    op.drop_table("investigation_jobs")
    op.drop_table("investigations")
    op.drop_table("webhook_deliveries")
    op.drop_table("github_installations")
    op.drop_table("app_settings")
    op.drop_table("user_sessions")
    op.drop_table("users")
