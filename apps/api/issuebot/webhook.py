"""Verify a GitHub delivery and enqueue at most one investigation for it."""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from issuebot.db import utcnow
from issuebot.models import GithubInstallation, Investigation, InvestigationJob, WebhookDelivery
from issuebot.runtime import load_runtime
from issuebot.safety import github_signature_matches, plain_text
from issuebot.settings import Settings

log = logging.getLogger("issuebot.webhook")
MAX_BODY = 1_000_000


def accept_webhook(
    session: Session, settings: Settings, body: bytes, headers: dict[str, str]
) -> tuple[int, dict]:
    if len(body) > MAX_BODY:
        return 413, {"error": "payload_too_large", "message": "Webhook body exceeds 1 MB."}
    config = load_runtime(session, settings)
    signature = headers.get("x-hub-signature-256", "")
    if not github_signature_matches(config.github_webhook_secret, body, signature):
        log.info("webhook signature rejected")
        return 401, {"error": "invalid_signature", "message": "Webhook signature did not match."}
    delivery_id = headers.get("x-github-delivery", "").strip()
    event = headers.get("x-github-event", "").strip()
    if not delivery_id or not event or len(delivery_id) > 80:
        return 400, {
            "error": "missing_headers",
            "message": "X-GitHub-Delivery and X-GitHub-Event are required.",
        }
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return 400, {"error": "invalid_json", "message": "Webhook body is not valid JSON."}
    if not isinstance(payload, dict):
        return 400, {"error": "invalid_json", "message": "Webhook body must be a JSON object."}

    action = payload.get("action") if isinstance(payload.get("action"), str) else None
    delivery = WebhookDelivery(
        delivery_id=delivery_id,
        event=event[:64],
        action=action[:64] if action else None,
        received_at=utcnow(),
        outcome="ignored",
        ignore_reason=None,
    )
    session.add(delivery)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return 202, {"status": "duplicate"}

    _sync_installation(session, payload, event, action)
    if event == "installation":
        delivery.outcome = "ignored"
        delivery.ignore_reason = "installation_event"
        session.commit()
        return 202, {"status": "ignored", "reason": "installation_event"}
    if event != "issues" or action != "opened":
        delivery.ignore_reason = "unsupported_event"
        session.commit()
        return 202, {"status": "ignored", "reason": "unsupported_event"}

    repository = _mapping(payload.get("repository"))
    issue = _mapping(payload.get("issue"))
    full_name = repository.get("full_name")
    repo = full_name if isinstance(full_name, str) else ""
    number = issue.get("number")
    installation = _mapping(payload.get("installation"))
    installation_id = installation.get("id")
    allowed = {item.lower() for item in config.allowed_repos}
    if not repo or repo.lower() not in allowed:
        delivery.ignore_reason = "repo_not_allowed"
        session.commit()
        return 202, {"status": "ignored", "reason": "repo_not_allowed"}
    if not isinstance(number, int) or not isinstance(installation_id, int):
        delivery.ignore_reason = "missing_issue"
        session.commit()
        return 202, {"status": "ignored", "reason": "missing_issue"}
    installation_row = session.get(GithubInstallation, installation_id)
    if installation_row and installation_row.status != "active":
        delivery.ignore_reason = "installation_inactive"
        session.commit()
        return 202, {"status": "ignored", "reason": "installation_inactive"}

    now = utcnow()
    user = _mapping(issue.get("user"))
    labels = []
    for label in issue.get("labels") or []:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            labels.append(label["name"])
    investigation = Investigation(
        id=uuid.uuid4(),
        delivery_id=delivery_id,
        installation_id=installation_id,
        repository_id=repository.get("id") if isinstance(repository.get("id"), int) else None,
        repo_full_name=repo,
        issue_number=number,
        issue_url=str(issue.get("html_url") or f"https://github.com/{repo}/issues/{number}"),
        issue_title=plain_text(str(issue.get("title") or ""), 500),
        issue_body=plain_text(str(issue.get("body") or ""), settings.max_issue_chars),
        issue_author=_text(user.get("login"), 200),
        issue_labels=labels[:20],
        status="queued",
        attempt_count=0,
        manual_retries=0,
        created_at=now,
        updated_at=now,
    )
    session.add(investigation)
    session.add(
        InvestigationJob(
            investigation_id=investigation.id,
            status="pending",
            attempts=0,
            run_after=now,
        )
    )
    delivery.outcome = "enqueued"
    session.commit()
    log.info("webhook enqueued investigation=%s repo=%s issue=%s", investigation.id, repo, number)
    return 202, {"status": "enqueued", "investigation_id": str(investigation.id)}


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: object, limit: int) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _sync_installation(session: Session, payload: dict, event: str, action: str | None) -> None:
    installation = _mapping(payload.get("installation"))
    installation_id = installation.get("id")
    if not isinstance(installation_id, int):
        return
    account = _mapping(installation.get("account"))
    login = _text(account.get("login"), 200)
    row = session.get(GithubInstallation, installation_id)
    if row is None:
        row = GithubInstallation(
            installation_id=installation_id,
            account_login=login,
            status="active",
            updated_at=utcnow(),
        )
        session.add(row)
    elif login:
        row.account_login = login
    if event == "installation":
        if action == "deleted":
            row.status = "deleted"
        elif action == "suspend":
            row.status = "suspended"
        elif action in {"created", "unsuspend", "new_permissions_accepted"}:
            row.status = "active"
    row.updated_at = utcnow()
