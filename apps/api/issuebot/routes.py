"""HTTP routes. State-changing calls require a session and X-IssueBot-Request."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from issuebot.auth import change_password, current_user, login, logout, require_csrf
from issuebot.crypto import CryptoError, encrypt_secret
from issuebot.db import isoformat, utcnow
from issuebot.docsgpt import DocsGPTClient
from issuebot.errors import IntegrationError, api_error, safe_message
from issuebot.github import GitHubClient
from issuebot.models import (
    AppSettings,
    AuditEvent,
    GithubInstallation,
    Investigation,
    PublishedComment,
    User,
)
from issuebot.publishing import comment_preview, publish_block_reason, publish_comment
from issuebot.runtime import load_runtime, private_key_from_env
from issuebot.safety import valid_repo_name
from issuebot.settings import Settings
from issuebot.webhook import accept_webhook
from issuebot.worker import delete_investigation, enqueue_sample, retry_investigation

log = logging.getLogger("issuebot.api")
health_router = APIRouter(prefix="/api/health")
public_router = APIRouter(prefix="/api/v1")
authed_router = APIRouter(prefix="/api/v1")


def get_db(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    require_csrf(request)
    return current_user(request, db)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class SettingsIn(BaseModel):
    docsgpt_base_url: str | None = Field(default=None, max_length=500)
    docsgpt_agent_id: str | None = Field(default=None, max_length=200)
    docsgpt_api_key: str | None = Field(default=None, max_length=500)
    github_app_id: str | None = Field(default=None, max_length=64)
    github_private_key: str | None = Field(default=None, max_length=20000)
    github_webhook_secret: str | None = Field(default=None, max_length=500)
    allowed_repos: list[str] | None = None
    publish_enabled: bool | None = None


class PublishIn(BaseModel):
    acknowledged: bool
    content_sha256: str = Field(min_length=64, max_length=64)


@health_router.get("/live")
def live() -> dict:
    return {"status": "live"}


@health_router.get("/ready")
def ready(request: Request, db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
    except Exception:
        log.error("readiness database check failed")
        return Response(
            content='{"status":"unavailable","database":"unavailable","worker":"unknown"}',
            status_code=503,
            media_type="application/json",
        )
    settings = request.app.state.settings
    if not settings.worker_enabled:
        return {"status": "ok", "database": "ok", "worker": "disabled"}
    age = time.time() - float(request.app.state.worker_heartbeat or 0)
    if age > 30:
        return Response(
            content='{"status":"unavailable","database":"ok","worker":"stale"}',
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ok", "database": "ok", "worker": "ok"}


@public_router.post("/auth/login")
def auth_login(
    payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    require_csrf(request)
    login(db, response, request.app.state.settings, payload.username, payload.password)
    return {"status": "signed_in"}


@public_router.post("/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    status, payload = await _accept(request.app, body, headers)
    if payload.get("status") == "enqueued":
        request.app.state.wake.set()
    return Response(status_code=status, content=_json(payload), media_type="application/json")


@authed_router.post("/auth/logout")
def auth_logout(
    response: Response,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    logout(db, request, response, user)
    return {"status": "signed_out"}


@authed_router.get("/auth/me")
def auth_me(user: User = Depends(require_user), settings: Settings = Depends(get_settings)):
    return {"username": user.username, "demo_mode": settings.demo_mode}


@authed_router.post("/account/password")
def auth_password(
    payload: PasswordIn, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    change_password(db, user, payload.current_password, payload.new_password)
    return {"status": "password_changed"}


@authed_router.get("/overview")
def overview(user: User = Depends(require_user), db: Session = Depends(get_db)):
    del user
    counts = {status: 0 for status in ("queued", "running", "completed", "failed")}
    rows = db.execute(
        select(Investigation.status, func.count()).group_by(Investigation.status)
    ).all()
    for status, count in rows:
        if status in counts:
            counts[status] = count
    published_ids = select(PublishedComment.investigation_id).where(
        PublishedComment.github_comment_id.is_not(None)
    )
    awaiting = db.scalar(
        select(func.count())
        .select_from(Investigation)
        .where(
            Investigation.status == "completed",
            Investigation.id.not_in(published_ids),
        )
    )
    published = db.scalar(
        select(func.count())
        .select_from(PublishedComment)
        .where(PublishedComment.github_comment_id.is_not(None))
    )
    recent = db.scalars(
        select(Investigation).order_by(Investigation.created_at.desc()).limit(8)
    ).all()
    failed = db.scalars(
        select(Investigation)
        .where(Investigation.status == "failed")
        .order_by(Investigation.updated_at.desc())
        .limit(8)
    ).all()
    return {
        "counts": {
            **counts,
            "awaiting_approval": awaiting or 0,
            "comment_published": published or 0,
        },
        "recent": [_summary(db, item) for item in recent],
        "failed": [_summary(db, item) for item in failed],
    }


@authed_router.get("/investigations")
def list_investigations(
    repo: str | None = None,
    status: str | None = None,
    issue_number: int | None = None,
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    del user
    if limit < 1 or limit > 50 or offset < 0:
        raise api_error(
            400, "invalid_request", "Limit must be 1-50 and offset must be non-negative."
        )
    stmt = select(Investigation)
    if repo:
        stmt = stmt.where(func.lower(Investigation.repo_full_name) == repo.lower())
    if issue_number is not None:
        stmt = stmt.where(Investigation.issue_number == issue_number)
    if q:
        stmt = stmt.where(func.lower(Investigation.issue_title).contains(q.lower()[:200]))
    start = _parse_time(created_from)
    end = _parse_time(created_to)
    if start:
        stmt = stmt.where(Investigation.created_at >= start)
    if end:
        stmt = stmt.where(Investigation.created_at <= end)
    published_ids = select(PublishedComment.investigation_id).where(
        PublishedComment.github_comment_id.is_not(None)
    )
    if status == "awaiting_approval":
        stmt = stmt.where(
            Investigation.status == "completed", Investigation.id.not_in(published_ids)
        )
    elif status == "comment_published":
        stmt = stmt.where(Investigation.id.in_(published_ids))
    elif status:
        if status not in {"queued", "running", "completed", "failed"}:
            raise api_error(400, "invalid_request", "Unknown status filter.")
        stmt = stmt.where(Investigation.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Investigation.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "items": [_summary(db, item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@authed_router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    del user
    investigation = _get_or_404(db, investigation_id)
    config = load_runtime(db, request.app.state.settings)
    published = (
        db.query(PublishedComment).filter_by(investigation_id=investigation.id).one_or_none()
    )
    audits = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.target == f"investigation:{investigation.id}")
        .order_by(AuditEvent.id)
    ).all()
    preview = None
    if investigation.status == "completed" and investigation.report:
        preview = comment_preview(investigation)
    return {
        **_summary(db, investigation),
        "issue_body": investigation.issue_body,
        "issue_author": investigation.issue_author,
        "issue_labels": investigation.issue_labels,
        "report": investigation.report,
        "attempt_count": investigation.attempt_count,
        "manual_retries": investigation.manual_retries,
        "audit": [
            {
                "actor": event.actor,
                "action": event.action,
                "created_at": isoformat(event.created_at),
                "detail": event.detail,
            }
            for event in audits
        ],
        "published_comment": None
        if published is None
        else {
            "state": published.state,
            "github_comment_id": published.github_comment_id,
            "comment_url": published.comment_url,
            "content_sha256": published.content_sha256,
            "approved_by": published.approved_by,
        },
        "comment_preview": preview,
        "actions": {
            "publish_allowed": publish_block_reason(investigation, config, db) is None,
            "publish_block_reason": publish_block_reason(investigation, config, db),
            "retry_allowed": investigation.status == "failed"
            and investigation.manual_retries < request.app.state.settings.manual_retry_limit,
            "demo_mode": config.demo_mode,
        },
    }


@authed_router.post("/investigations/{investigation_id}/retry")
def retry(
    investigation_id: str,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        retry_investigation(
            db, investigation_id, user.username, request.app.state.settings.manual_retry_limit
        )
    except KeyError:
        raise api_error(404, "not_found", "Investigation not found.") from None
    except ValueError as exc:
        code = str(exc)
        if code == "retry_limit":
            raise api_error(
                409, "retry_limit", "This investigation has reached the manual retry limit."
            ) from None
        raise api_error(409, "not_failed", "Only a failed investigation can be retried.") from None
    request.app.state.wake.set()
    return {"status": "queued"}


@authed_router.delete("/investigations/{investigation_id}")
def remove(
    investigation_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    try:
        delete_investigation(db, investigation_id, user.username)
    except KeyError:
        raise api_error(404, "not_found", "Investigation not found.") from None
    return {"status": "deleted"}


@authed_router.post("/investigations/{investigation_id}/comment-preview")
def preview(
    investigation_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    investigation = _get_or_404(db, investigation_id)
    try:
        return comment_preview(investigation)
    except ValueError:
        raise api_error(
            409, "not_ready", "A comment can be previewed after the investigation completes."
        ) from None


@authed_router.post("/investigations/{investigation_id}/publish-comment")
def publish(
    investigation_id: str,
    payload: PublishIn,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return publish_comment(
            request.app,
            db,
            investigation_id,
            user.username,
            payload.acknowledged,
            payload.content_sha256,
        )
    except KeyError:
        raise api_error(404, "not_found", "Investigation not found.") from None
    except PermissionError as exc:
        raise api_error(409, "publish_blocked", str(exc)) from None
    except ValueError as exc:
        code = str(exc)
        messages = {
            "not_acknowledged": "Confirm that you reviewed the comment before publishing.",
            "stale_preview": "The comment changed. Refresh the preview and try again.",
            "publish_in_progress": "A publish for this investigation is already in progress.",
        }
        raise api_error(409, code, messages.get(code, "The comment was not published.")) from None
    except IntegrationError as exc:
        raise api_error(502, exc.code, safe_message(exc.code)) from None


@authed_router.get("/settings")
def get_settings_view(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    settings = request.app.state.settings
    row = db.get(AppSettings, 1)
    if row is None:
        raise api_error(500, "internal_error", "Settings are not initialized.")
    config = load_runtime(db, settings)
    return _settings_view(settings, row, config, db)


@authed_router.put("/settings")
def put_settings(
    payload: SettingsIn,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    row = db.get(AppSettings, 1)
    if row is None:
        raise api_error(500, "internal_error", "Settings are not initialized.")
    changed: list[str] = []
    if payload.docsgpt_base_url is not None:
        _validate_docsgpt_url(payload.docsgpt_base_url, settings)
        row.docsgpt_base_url = payload.docsgpt_base_url.strip()
        changed.append("docsgpt_base_url")
    if payload.docsgpt_agent_id is not None:
        row.docsgpt_agent_id = payload.docsgpt_agent_id.strip()
        changed.append("docsgpt_agent_id")
    if payload.github_app_id is not None:
        app_id = payload.github_app_id.strip()
        if app_id and not app_id.isdigit():
            raise api_error(400, "invalid_request", "GitHub App ID must be numeric.")
        row.github_app_id = app_id
        changed.append("github_app_id")
    if payload.allowed_repos is not None:
        repos = []
        for repo in payload.allowed_repos:
            if not valid_repo_name(repo):
                raise api_error(
                    400, "invalid_request", "Repository names must look like owner/name."
                )
            repos.append(repo)
        row.allowed_repos = repos
        changed.append("allowed_repos")
    if payload.publish_enabled is not None:
        row.publish_enabled = payload.publish_enabled
        changed.append("publish_enabled")
    _store_secret(
        settings,
        row,
        "docsgpt_api_key_ciphertext",
        payload.docsgpt_api_key,
        changed,
        "docsgpt_api_key",
    )
    _store_secret(
        settings,
        row,
        "github_private_key_ciphertext",
        payload.github_private_key,
        changed,
        "github_private_key",
    )
    _store_secret(
        settings,
        row,
        "github_webhook_secret_ciphertext",
        payload.github_webhook_secret,
        changed,
        "github_webhook_secret",
    )
    if payload.github_private_key and "PRIVATE KEY" not in payload.github_private_key:
        raise api_error(400, "invalid_request", "The GitHub private key must be a PEM private key.")
    row.updated_at = utcnow()
    db.add(
        AuditEvent(
            actor=user.username,
            action="settings.updated",
            target="settings",
            detail={"fields": changed},
            created_at=utcnow(),
        )
    )
    db.commit()
    return _settings_view(settings, row, load_runtime(db, settings), db)


@authed_router.post("/settings/test-docsgpt")
def test_docsgpt(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    config = load_runtime(db, request.app.state.settings)
    client = DocsGPTClient(
        config,
        request.app.state.settings,
        transport=request.app.state.docsgpt_transport,
        sleeper=request.app.state.sleeper,
        resolver=request.app.state.resolver,
    )
    try:
        if config.demo_mode:
            return {
                "ok": True,
                "demo": True,
                "message": "Demo mode: no live DocsGPT call was made.",
            }
        result = client.answer("Reply with the single word pong.")
    except IntegrationError as exc:
        return {"ok": False, "demo": False, "error": exc.code, "message": safe_message(exc.code)}
    finally:
        client.close()
    return {
        "ok": True,
        "demo": False,
        "message": "DocsGPT responded.",
        "source_count": len(result.sources),
        "conversation_recorded": bool(result.conversation_id),
    }


@authed_router.post("/settings/test-github")
def test_github(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    config = load_runtime(db, request.app.state.settings)
    client = GitHubClient(
        config,
        request.app.state.settings,
        transport=request.app.state.github_transport,
        sleeper=request.app.state.sleeper,
        resolver=request.app.state.resolver,
    )
    try:
        result = client.test_app()
    except IntegrationError as exc:
        return {
            "ok": False,
            "demo": config.demo_mode,
            "error": exc.code,
            "message": safe_message(exc.code),
        }
    finally:
        client.close()
    return {
        "ok": True,
        "demo": config.demo_mode,
        "message": "GitHub accepted the app credentials.",
        "app_name": result.get("app_name"),
        "app_id": result.get("app_id"),
    }


@authed_router.get("/health")
def health_view(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    settings = request.app.state.settings
    config = load_runtime(db, settings)
    database = "ok"
    try:
        db.execute(select(1))
    except Exception:
        database = "unavailable"
    if not settings.worker_enabled:
        worker = "disabled"
    elif time.time() - float(request.app.state.worker_heartbeat or 0) > 30:
        worker = "stale"
    else:
        worker = "ok"
    return {
        "api": "ok",
        "database": database,
        "worker": worker,
        "docsgpt": "demo"
        if config.demo_mode
        else (
            "configured" if config.docsgpt_api_key and config.docsgpt_base_url else "not_configured"
        ),
        "github": "demo"
        if config.demo_mode
        else (
            "configured" if config.github_app_id and config.github_private_key else "not_configured"
        ),
        "publish_enabled": config.publish_enabled,
        "allow_private_docsgpt": settings.allow_private_docsgpt,
    }


@authed_router.post("/demo/sample-issue")
def sample_issue(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    del user
    if not request.app.state.settings.demo_mode:
        raise api_error(404, "not_found", "Sample issues are only available in demo mode.")
    try:
        investigation = enqueue_sample(db, request.app.state.settings)
    except ValueError:
        raise api_error(
            409, "allowlist", "Add acme/widget to the repository allowlist before loading a sample."
        ) from None
    request.app.state.wake.set()
    return {"status": "queued", "investigation_id": str(investigation.id)}


def _settings_view(settings: Settings, row: AppSettings, config, db: Session) -> dict:
    installations = db.scalars(
        select(GithubInstallation).order_by(GithubInstallation.installation_id)
    ).all()
    return {
        "demo_mode": settings.demo_mode,
        "env": settings.env,
        "public_base_url": settings.public_base_url,
        "webhook_url": settings.public_base_url + "/api/v1/webhooks/github",
        "docsgpt_base_url": config.docsgpt_base_url,
        "docsgpt_agent_id": config.docsgpt_agent_id,
        "docsgpt_api_key_configured": bool(
            row.docsgpt_api_key_ciphertext or settings.docsgpt_api_key
        ),
        "github_app_id": config.github_app_id,
        "github_private_key_configured": bool(
            row.github_private_key_ciphertext or private_key_from_env(settings)
        ),
        "github_webhook_secret_configured": bool(
            row.github_webhook_secret_ciphertext or settings.github_webhook_secret
        ),
        "allowed_repos": config.allowed_repos,
        "publish_enabled": bool(row.publish_enabled),
        "publish_effective": config.publish_enabled,
        "allow_private_docsgpt": settings.allow_private_docsgpt,
        "worker_enabled": settings.worker_enabled,
        "installations": [
            {
                "installation_id": item.installation_id,
                "account_login": item.account_login,
                "status": item.status,
            }
            for item in installations
        ],
    }


def _store_secret(
    settings: Settings,
    row: AppSettings,
    column: str,
    value: str | None,
    changed: list[str],
    name: str,
) -> None:
    if value is None or value == "":
        return
    if name == "github_private_key" and "PRIVATE KEY" not in value:
        raise api_error(400, "invalid_request", "The GitHub private key must be a PEM private key.")
    try:
        setattr(row, column, encrypt_secret(settings.fernet_key, value))
    except CryptoError:
        raise api_error(
            400, "fernet_key_missing", "Set ISSUEBOT_FERNET_KEY before saving a secret."
        ) from None
    changed.append(name)


def _validate_docsgpt_url(url: str, settings: Settings) -> None:
    if url.strip() == "":
        return
    from issuebot.safety import UnsafeURL, assess_url

    try:
        assess_url(
            url.strip() + "/api/answer",
            production=settings.production,
            allow_private=settings.allow_private_docsgpt,
            resolver=_settings_resolver(settings),
        )
    except UnsafeURL:
        raise api_error(
            400, "unsafe_url", "That DocsGPT URL is not allowed by the outbound policy."
        ) from None


def _settings_resolver(settings: Settings):
    import socket

    def resolver(host: str, port: int):
        if not settings.production:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    return resolver


def _summary(db: Session, investigation: Investigation) -> dict:
    published = (
        db.query(PublishedComment).filter_by(investigation_id=investigation.id).one_or_none()
    )
    return {
        "id": str(investigation.id),
        "repo_full_name": investigation.repo_full_name,
        "issue_number": investigation.issue_number,
        "issue_title": investigation.issue_title,
        "issue_url": investigation.issue_url,
        "status": investigation.status,
        "display_status": _display_status(investigation, published),
        "error_code": investigation.error_code,
        "error_message": investigation.error_message,
        "created_at": isoformat(investigation.created_at),
        "updated_at": isoformat(investigation.updated_at),
        "mock": bool((investigation.report or {}).get("mock")),
    }


def _display_status(investigation: Investigation, published: PublishedComment | None) -> str:
    if published is not None and published.github_comment_id:
        return "comment_published"
    if investigation.status == "completed":
        return "awaiting_approval"
    return investigation.status


def _get_or_404(db: Session, investigation_id: str) -> Investigation:
    try:
        parsed = uuid.UUID(investigation_id)
    except ValueError:
        raise api_error(404, "not_found", "Investigation not found.") from None
    investigation = db.get(Investigation, parsed)
    if investigation is None:
        raise api_error(404, "not_found", "Investigation not found.")
    return investigation


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise api_error(400, "invalid_request", "Dates must be ISO-8601.") from None
    return parsed


async def _accept(app, body: bytes, headers: dict[str, str]) -> tuple[int, dict]:
    import asyncio

    def run():
        session = app.state.session_factory()
        try:
            return accept_webhook(session, app.state.settings, body, headers)
        except Exception:
            session.rollback()
            log.error("webhook storage failed")
            return 500, {"error": "internal_error", "message": "The webhook could not be stored."}
        finally:
            session.close()

    return await asyncio.to_thread(run)


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload)
