"""Publish a reviewed comment only after an authenticated confirmation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from issuebot.db import as_utc, utcnow
from issuebot.errors import IntegrationError
from issuebot.github import GitHubClient, clear_token_cache
from issuebot.models import AuditEvent, GithubInstallation, Investigation, PublishedComment
from issuebot.report import content_hash, render_comment
from issuebot.runtime import RuntimeConfig, load_runtime
from issuebot.settings import Settings

log = logging.getLogger("issuebot.publishing")


def _publish_locked(existing: PublishedComment, now: datetime) -> bool:
    updated = as_utc(existing.updated_at)
    return bool(
        existing.state == "publishing"
        and updated is not None
        and updated > now - timedelta(minutes=2)
    )


def comment_preview(investigation: Investigation) -> dict:
    if investigation.report is None or investigation.status != "completed":
        raise ValueError("not_ready")
    body = render_comment(
        str(investigation.id),
        investigation.repo_full_name,
        investigation.issue_number,
        investigation.report,
    )
    return {
        "body": body,
        "content_sha256": content_hash(body),
        "repo_full_name": investigation.repo_full_name,
        "issue_number": investigation.issue_number,
        "issue_url": investigation.issue_url,
    }


def publish_block_reason(
    investigation: Investigation, config: RuntimeConfig, session: Session
) -> str | None:
    if config.demo_mode:
        return "Demo mode never publishes to GitHub."
    if not config.publish_enabled:
        return "Publishing is off. Turn it on in Settings."
    if investigation.status != "completed" or investigation.report is None:
        return "The investigation has not completed."
    existing = (
        session.query(PublishedComment).filter_by(investigation_id=investigation.id).one_or_none()
    )
    if existing and existing.github_comment_id:
        return "A comment was already published."
    allowed = {item.lower() for item in config.allowed_repos}
    if investigation.repo_full_name.lower() not in allowed:
        return "This repository is not on the allowlist."
    if investigation.installation_id is None:
        return "The GitHub installation is missing."
    installation = session.get(GithubInstallation, investigation.installation_id)
    if installation is None or installation.status != "active":
        return "The GitHub installation is not active."
    return None


def publish_comment(
    app, session: Session, investigation_id: str, actor: str, acknowledged: bool, digest: str
) -> dict:
    if not acknowledged:
        raise ValueError("not_acknowledged")
    settings: Settings = app.state.settings
    config = load_runtime(session, settings)
    investigation = _load(session, investigation_id)
    reason = publish_block_reason(investigation, config, session)
    existing = (
        session.query(PublishedComment).filter_by(investigation_id=investigation.id).one_or_none()
    )
    if existing and existing.github_comment_id:
        return _payload(existing)
    if reason:
        raise PermissionError(reason)
    preview = comment_preview(investigation)
    if preview["content_sha256"] != digest:
        raise ValueError("stale_preview")
    now = utcnow()
    if existing is None:
        existing = PublishedComment(
            investigation_id=investigation.id,
            state="publishing",
            content_sha256=digest,
            body=preview["body"],
            approved_by=actor,
            created_at=now,
            updated_at=now,
        )
        session.add(existing)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError("publish_in_progress") from exc
    elif _publish_locked(existing, now):
        raise ValueError("publish_in_progress")
    else:
        existing.state = "publishing"
        existing.content_sha256 = digest
        existing.body = preview["body"]
        existing.approved_by = actor
        existing.updated_at = now
        session.commit()

    github = GitHubClient(
        config,
        settings,
        transport=app.state.github_transport,
        sleeper=app.state.sleeper,
        resolver=app.state.resolver,
    )
    installation_id = investigation.installation_id
    if installation_id is None:
        raise ValueError("missing_installation")
    marker = f"<!-- issuebot:{investigation.id} -->"
    try:
        found = github.find_marker(
            installation_id,
            investigation.repo_full_name,
            investigation.issue_number,
            investigation.repository_id,
            marker,
        )
        if found is None:
            found = github.create_comment(
                installation_id,
                investigation.repo_full_name,
                investigation.issue_number,
                investigation.repository_id,
                preview["body"],
            )
    except IntegrationError as exc:
        existing.state = "failed"
        existing.updated_at = utcnow()
        _audit(session, actor, "comment.publish_failed", investigation.id, {"error_code": exc.code})
        session.commit()
        log.info("publish failed investigation=%s code=%s", investigation.id, exc.code)
        raise
    finally:
        github.close()
        clear_token_cache()
    existing.state = "published"
    existing.github_comment_id = found["id"]
    existing.comment_url = found["url"]
    existing.updated_at = utcnow()
    _audit(
        session,
        actor,
        "comment.published",
        investigation.id,
        {"content_sha256": digest, "github_comment_id": found["id"]},
    )
    session.commit()
    return _payload(existing)


def _payload(row: PublishedComment) -> dict:
    return {
        "state": "published" if row.github_comment_id else row.state,
        "github_comment_id": row.github_comment_id,
        "comment_url": row.comment_url,
        "content_sha256": row.content_sha256,
        "approved_by": row.approved_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _load(session: Session, investigation_id: str) -> Investigation:
    try:
        parsed = uuid.UUID(investigation_id)
    except ValueError as exc:
        raise KeyError(investigation_id) from exc
    investigation = session.get(Investigation, parsed)
    if investigation is None:
        raise KeyError(investigation_id)
    return investigation


def _audit(
    session: Session, actor: str, action: str, investigation_id: uuid.UUID, detail: dict
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            target=f"investigation:{investigation_id}",
            detail=detail,
            created_at=utcnow(),
        )
    )
