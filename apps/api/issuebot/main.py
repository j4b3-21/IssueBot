"""IssueBot ASGI application."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from issuebot.db import make_engine, make_session_factory
from issuebot.logging_config import configure_logging
from issuebot.models import Investigation
from issuebot.routes import authed_router, health_router, public_router
from issuebot.runtime import bootstrap
from issuebot.settings import Settings, get_settings
from issuebot.worker import enqueue_sample, worker_loop

log = logging.getLogger("issuebot")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    app = FastAPI(title="IssueBot", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.wake = asyncio.Event()
    app.state.worker_heartbeat = 0.0
    app.state.docsgpt_transport = None
    app.state.github_transport = None
    app.state.sleeper = time.sleep
    app.state.resolver = socket.getaddrinfo
    origins = [settings.public_base_url]
    if not settings.production:
        origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-IssueBot-Request"],
    )
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
    app.middleware("http")(limit_body)
    app.include_router(health_router)
    app.include_router(public_router)
    app.include_router(authed_router)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    upgrade_database(app.state.settings.database_url)
    session = app.state.session_factory()
    try:
        bootstrap(session, app.state.settings)
        if app.state.settings.demo_mode:
            count = session.scalar(select(func.count()).select_from(Investigation)) or 0
            if count == 0:
                enqueue_sample(session, app.state.settings)
    finally:
        session.close()
    stop = asyncio.Event()
    task = None
    app.state.worker_heartbeat = time.time()
    if app.state.settings.worker_enabled:
        task = asyncio.create_task(worker_loop(app, stop))
    yield
    if task is not None:
        stop.set()
        app.state.wake.set()
        await task
    app.state.engine.dispose()


def upgrade_database(url: str) -> None:
    ini = _alembic_ini()
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def _alembic_ini() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        candidate = parent / "alembic.ini"
        if candidate.is_file():
            return candidate
    raise RuntimeError("alembic.ini was not found")


async def limit_body(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 1_000_000:
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large", "message": "Request body exceeds 1 MB."},
        )
    return await call_next(request)


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields = []
    for error in exc.errors():
        loc = error.get("loc") or ()
        fields.append(".".join(str(part) for part in loc))
    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_request",
            "message": "The request was not valid.",
            "fields": fields,
        },
    )


async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled error type=%s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Something went wrong."},
    )


app = create_app()
