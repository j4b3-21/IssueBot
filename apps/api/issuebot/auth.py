"""Single local administrator. The password hash is scrypt; the session cookie is random."""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from issuebot.db import as_utc, utcnow
from issuebot.models import AuditEvent, User, UserSession
from issuebot.safety import hash_password, hash_token, verify_password
from issuebot.settings import Settings

SESSION_HOURS = 12
LOCK_MINUTES = 15
MAX_FAILURES = 5
COOKIE = "issuebot_session"


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.headers.get("x-issuebot-request") != "1":
        raise HTTPException(
            status_code=403,
            detail={"error": "csrf", "message": "Missing X-IssueBot-Request header."},
        )


def current_user(request: Request, db: Session) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(
            status_code=401, detail={"error": "unauthenticated", "message": "Sign in required."}
        )
    row = db.get(UserSession, hash_token(token))
    expires_at = as_utc(row.expires_at) if row is not None else None
    if row is None or expires_at is None or expires_at < utcnow():
        if row is not None:
            db.delete(row)
            db.commit()
        raise HTTPException(
            status_code=401, detail={"error": "unauthenticated", "message": "Sign in required."}
        )
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(
            status_code=401, detail={"error": "unauthenticated", "message": "Sign in required."}
        )
    return user


def login(
    db: Session, response: Response, settings: Settings, username: str, password: str
) -> None:
    user = db.scalar(select(User).where(User.username == username))
    now = utcnow()
    locked_until = user.locked_until if user is not None else None
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=now.tzinfo)
    if user is not None and locked_until is not None and locked_until > now:
        raise HTTPException(
            status_code=429,
            detail={"error": "locked", "message": "Too many sign-in attempts. Try again later."},
        )
    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            _register_failure(db, user)
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )
    user.failed_logins = 0
    user.locked_until = None
    now = utcnow()
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=now + timedelta(hours=SESSION_HOURS),
        )
    )
    db.add(
        AuditEvent(
            actor=user.username,
            action="auth.login",
            target=f"user:{user.id}",
            detail={},
            created_at=now,
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_url.startswith("https://"),
        max_age=SESSION_HOURS * 3600,
        path="/",
    )


def logout(db: Session, request: Request, response: Response, user: User) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        row = db.get(UserSession, hash_token(token))
        if row is not None:
            db.delete(row)
    db.add(
        AuditEvent(
            actor=user.username,
            action="auth.logout",
            target=f"user:{user.id}",
            detail={},
            created_at=utcnow(),
        )
    )
    db.commit()
    response.delete_cookie(COOKIE, path="/")


def change_password(db: Session, user: User, current: str, new_password: str) -> None:
    if len(new_password) < 12:
        raise HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "Use at least 12 characters."},
        )
    if not verify_password(current, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )
    user.password_hash = hash_password(new_password)
    db.add(
        AuditEvent(
            actor=user.username,
            action="auth.password_changed",
            target=f"user:{user.id}",
            detail={},
            created_at=utcnow(),
        )
    )
    db.commit()


def _register_failure(db: Session, user: User) -> None:
    user.failed_logins += 1
    if user.failed_logins >= MAX_FAILURES:
        user.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
        user.failed_logins = 0
    db.add(
        AuditEvent(
            actor=user.username,
            action="auth.login_failed",
            target=f"user:{user.id}",
            detail={},
            created_at=utcnow(),
        )
    )
    db.commit()
