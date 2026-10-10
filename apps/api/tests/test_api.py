"""Webhook, auth, investigation, and publish behavior."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
from fastapi.testclient import TestClient
from issuebot.models import Investigation, InvestigationJob, PublishedComment
from issuebot.worker import claim_and_run_once
from sqlalchemy import select

from tests.conftest import auth_headers, docsgpt_handler, github_handler, issue_payload, sign_in


def _signed(
    body: bytes,
    delivery: str = "delivery-1",
    event: str = "issues",
    secret: str = "test-webhook-secret",
):
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "X-Hub-Signature-256": f"sha256={digest}",
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
        "Content-Type": "application/json",
        "User-Agent": "GitHub-Hookshot/test",
    }


def _post_issue(
    client: TestClient,
    payload: dict | None = None,
    delivery: str = "delivery-1",
    raw: bytes | None = None,
):
    body = raw if raw is not None else json.dumps(payload or issue_payload()).encode()
    return client.post(
        "/api/v1/webhooks/github", content=body, headers=_signed(body, delivery=delivery)
    )


def test_webhook_rejects_bad_signatures(client):
    body = json.dumps(issue_payload()).encode()
    missing = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Delivery": "d", "X-GitHub-Event": "issues"},
    )
    assert missing.status_code == 401
    sha1 = _signed(body)
    sha1.pop("X-Hub-Signature-256")
    sha1["X-Hub-Signature"] = "sha1=abc"
    assert client.post("/api/v1/webhooks/github", content=body, headers=sha1).status_code == 401
    tampered = body + b" "
    assert (
        client.post(
            "/api/v1/webhooks/github",
            content=tampered,
            headers=_signed(body, delivery="tamper"),
        ).status_code
        == 401
    )


def test_webhook_enqueues_once_and_ignores_duplicates_and_other_events(client, app):
    calls: list = []
    app.state.docsgpt_transport = httpx.MockTransport(
        lambda request: calls.append(request) or httpx.Response(500)
    )
    first = _post_issue(client, delivery="same-delivery")
    assert first.status_code == 202
    assert first.json()["status"] == "enqueued"
    assert calls == []
    again = _post_issue(client, delivery="same-delivery")
    assert again.status_code == 202
    assert again.json()["status"] == "duplicate"
    session = app.state.session_factory()
    assert session.query(Investigation).count() == 1
    session.close()
    other = json.dumps(issue_payload(repo="other/repo")).encode()
    ignored = client.post(
        "/api/v1/webhooks/github", content=other, headers=_signed(other, delivery="other")
    )
    assert ignored.json()["reason"] == "repo_not_allowed"
    edited = json.dumps(issue_payload(action="edited")).encode()
    assert (
        client.post(
            "/api/v1/webhooks/github", content=edited, headers=_signed(edited, delivery="edited")
        ).json()["reason"]
        == "unsupported_event"
    )
    ping = b'{"zen":"test"}'
    assert (
        client.post(
            "/api/v1/webhooks/github",
            content=ping,
            headers=_signed(ping, delivery="ping", event="ping"),
        ).json()["reason"]
        == "unsupported_event"
    )
    assert (
        client.post(
            "/api/v1/webhooks/github",
            content=b"not-json",
            headers=_signed(b"not-json", delivery="bad"),
        ).status_code
        == 400
    )


def test_empty_webhook_secret_fails_closed(make_app):
    application = make_app(ISSUEBOT_GITHUB_WEBHOOK_SECRET="")
    with TestClient(application) as test_client:
        body = json.dumps(issue_payload()).encode()
        response = test_client.post(
            "/api/v1/webhooks/github", content=body, headers=_signed(body, secret="")
        )
        assert response.status_code == 401


def test_worker_builds_report_without_publishing_or_inventing_sources(client, app):
    github_calls: list = []
    docsgpt_calls: list = []
    app.state.github_transport = httpx.MockTransport(github_handler(github_calls))
    app.state.docsgpt_transport = httpx.MockTransport(docsgpt_handler(docsgpt_calls))
    created = _post_issue(client)
    assert created.json()["status"] == "enqueued"
    assert docsgpt_calls == []
    assert claim_and_run_once(app) is True
    assert docsgpt_calls
    assert "ghs_testtokenvalue" not in docsgpt_calls[0].content.decode()
    assert b"test-docsgpt-key" in docsgpt_calls[0].content
    comment_posts = [
        call for call in github_calls if call[0] == "POST" and call[1].endswith("/comments")
    ]
    assert comment_posts == []
    token_body = json.loads(github_calls[0][2])
    assert token_body["permissions"] == {"issues": "read"}
    assert token_body["repository_ids"] == [99]
    sign_in(client)
    detail = client.get(f"/api/v1/investigations/{created.json()['investigation_id']}")
    assert detail.status_code == 200
    report = detail.json()["report"]
    assert report["documented_facts"]
    assert report["hypotheses"]
    assert [item["url"] for item in report["sources"]] == ["https://docs.example.com/install"]
    assert "evil.example" not in json.dumps(report["sources"])
    assert report["related_issues"][0]["number"] == 3
    assert report["related_issues"][0]["reason"].endswith("This is not a duplicate verdict.")
    assert "ignore previous instructions" in detail.json()["issue_body"]
    assert detail.json()["display_status"] == "awaiting_approval"
    assert detail.json()["actions"]["publish_allowed"] is False


def test_failed_job_is_retryable(client, app, make_app):
    del make_app
    app.state.settings.job_max_attempts = 1
    app.state.github_transport = httpx.MockTransport(github_handler([]))
    app.state.docsgpt_transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"error": "down"})
    )
    created = _post_issue(client)
    assert claim_and_run_once(app) is True
    sign_in(client)
    detail = client.get(f"/api/v1/investigations/{created.json()['investigation_id']}")
    assert detail.json()["status"] == "failed"
    assert "secret" not in detail.json()["error_message"].lower()
    retried = client.post(
        f"/api/v1/investigations/{created.json()['investigation_id']}/retry", headers=auth_headers()
    )
    assert retried.status_code == 200
    session = app.state.session_factory()
    job = session.scalars(select(InvestigationJob)).one()
    assert job.status == "pending"
    assert job.attempts == 0
    session.close()


def test_auth_cookie_csrf_and_lockout(client):
    denied = client.get("/api/v1/overview")
    assert denied.status_code == 401
    missing_csrf = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "test-password-strong"}
    )
    assert missing_csrf.status_code == 403
    sign_in(client)
    cookie = client.cookies.get("issuebot_session")
    set_cookie = client.cookies
    assert cookie
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "test-password-strong"},
        headers=auth_headers(),
    )
    header = login.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert client.get("/api/v1/auth/me").json()["username"] == "admin"
    client.post("/api/v1/auth/logout", headers=auth_headers())
    assert client.get("/api/v1/overview").status_code == 401
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-password-value"},
            headers=auth_headers(),
        )
        assert response.status_code == 401
    locked = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password-value"},
        headers=auth_headers(),
    )
    assert locked.status_code == 429
    del set_cookie


def test_settings_do_not_return_secrets(client, app):
    sign_in(client)
    saved = client.put(
        "/api/v1/settings",
        json={"docsgpt_api_key": "super-secret-key-value", "publish_enabled": False},
        headers=auth_headers(),
    )
    assert saved.status_code == 200
    body = saved.text
    assert "super-secret-key-value" not in body
    assert saved.json()["docsgpt_api_key_configured"] is True
    session = app.state.session_factory()
    from issuebot.models import AppSettings

    row = session.get(AppSettings, 1)
    assert row.docsgpt_api_key_ciphertext
    assert "super-secret-key-value" not in row.docsgpt_api_key_ciphertext
    session.close()


def test_publish_requires_approval_and_is_idempotent(client, app):
    app.state.github_transport = httpx.MockTransport(github_handler([]))
    app.state.docsgpt_transport = httpx.MockTransport(docsgpt_handler([]))
    created = _post_issue(client)
    investigation_id = created.json()["investigation_id"]
    claim_and_run_once(app)
    sign_in(client)
    blocked = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment",
        json={"acknowledged": True, "content_sha256": "a" * 64},
        headers=auth_headers(),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "publish_blocked"
    enabled = client.put("/api/v1/settings", json={"publish_enabled": True}, headers=auth_headers())
    assert enabled.json()["publish_enabled"] is True
    preview = client.post(
        f"/api/v1/investigations/{investigation_id}/comment-preview", headers=auth_headers()
    )
    assert preview.status_code == 200
    assert "<!-- issuebot:" in preview.json()["body"]
    assert "@octocat" not in preview.json()["body"]
    recorder: list = []
    app.state.github_transport = httpx.MockTransport(github_handler(recorder))
    payload = {"acknowledged": True, "content_sha256": preview.json()["content_sha256"]}
    published = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment",
        json=payload,
        headers=auth_headers(),
    )
    assert published.status_code == 200, published.text
    assert published.json()["comment_url"].startswith("https://github.com/acme/widget/issues/7#")
    posts = [item for item in recorder if item[0] == "POST" and item[1].endswith("/comments")]
    assert len(posts) == 1
    posted = posts[0][2].decode()
    assert "ghs_testtokenvalue" not in posted
    assert "@octocat" not in json.loads(posted)["body"]
    write_mints = [
        json.loads(item[2])
        for item in recorder
        if item[0] == "POST" and item[1].endswith("/access_tokens") and b'"write"' in item[2]
    ]
    assert write_mints
    assert write_mints[0]["permissions"] == {"issues": "write"}
    again = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment",
        json=payload,
        headers=auth_headers(),
    )
    assert again.status_code == 200
    assert (
        len([item for item in recorder if item[0] == "POST" and item[1].endswith("/comments")]) == 1
    )
    no_csrf = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment", json=payload
    )
    assert no_csrf.status_code == 403


def test_publish_blocks_revoked_installation_and_removed_repo(client, app):
    app.state.github_transport = httpx.MockTransport(github_handler([]))
    app.state.docsgpt_transport = httpx.MockTransport(docsgpt_handler([]))
    created = _post_issue(client, delivery="revoked-delivery")
    investigation_id = created.json()["investigation_id"]
    claim_and_run_once(app)
    sign_in(client)
    client.put("/api/v1/settings", json={"publish_enabled": True}, headers=auth_headers())
    session = app.state.session_factory()
    from issuebot.models import GithubInstallation

    installation = session.get(GithubInstallation, 42)
    installation.status = "suspended"
    session.commit()
    session.close()
    preview = client.post(
        f"/api/v1/investigations/{investigation_id}/comment-preview", headers=auth_headers()
    ).json()
    blocked = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment",
        json={"acknowledged": True, "content_sha256": preview["content_sha256"]},
        headers=auth_headers(),
    )
    assert blocked.status_code == 409
    session = app.state.session_factory()
    installation = session.get(GithubInstallation, 42)
    installation.status = "active"
    session.commit()
    session.close()
    client.put(
        "/api/v1/settings",
        json={"allowed_repos": ["other/repo"], "publish_enabled": True},
        headers=auth_headers(),
    )
    removed = client.post(
        f"/api/v1/investigations/{investigation_id}/publish-comment",
        json={"acknowledged": True, "content_sha256": preview["content_sha256"]},
        headers=auth_headers(),
    )
    assert removed.status_code == 409
    session = app.state.session_factory()
    assert (
        session.query(PublishedComment)
        .filter(PublishedComment.github_comment_id.is_not(None))
        .count()
        == 0
    )
    session.close()


def test_anonymous_cannot_publish(client, app):
    app.state.github_transport = httpx.MockTransport(github_handler([]))
    app.state.docsgpt_transport = httpx.MockTransport(docsgpt_handler([]))
    created = _post_issue(client, delivery="anon")
    claim_and_run_once(app)
    response = client.post(
        f"/api/v1/investigations/{created.json()['investigation_id']}/publish-comment",
        json={"acknowledged": True, "content_sha256": "b" * 64},
        headers=auth_headers(),
    )
    assert response.status_code == 401


def test_health_and_overview(client):
    assert client.get("/api/health/live").json()["status"] == "live"
    assert client.get("/api/health/ready").json()["worker"] == "disabled"
    sign_in(client)
    overview = client.get("/api/v1/overview")
    assert overview.status_code == 200
    assert overview.json()["counts"]["queued"] == 0
    health = client.get("/api/v1/health")
    assert health.json()["database"] == "ok"
    assert "test-docsgpt-key" not in health.text
