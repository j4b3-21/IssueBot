# Development

Python 3.12 or newer and Node.js 22. The API image stays on Python 3.12 even if the host is newer. This workspace was developed on Python 3.14 with that constraint in the image.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e "apps/api[dev]"
cd apps/web && npm ci
```

Copy `.env.example` to `.env` for a full stack. Tests set `ISSUEBOT_IGNORE_ENV_FILE=1` and do not read `.env`.

## Run

API against SQLite for a quick demo:

```bash
export ISSUEBOT_ADMIN_PASSWORD='replace-with-12-plus-characters'
make demo
```

Dashboard:

```bash
cd apps/web && npm run dev
```

Vite proxies `/api`, `/docs`, `/openapi.json`, and `/redoc` to `http://127.0.0.1:8000`.

Compose:

```bash
docker compose up --build
```

## Checks

```bash
make test
make lint
make typecheck
cd apps/api && ../../.venv/bin/ruff format --check issuebot tests
cd apps/web && npm run build
```

Ruff line length is 100. E501 is ignored because a few signatures are long. Frontend formatting is Prettier with a width of 100.

## Migrations

Edit models, then from `apps/api`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Review the generated file. Keep types portable: JSON, Uuid, and BigInteger. Avoid PostgreSQL ENUM and JSONB so SQLite tests can migrate.

Startup also runs `upgrade head`. Use one API process.

## Where to change behavior

- HTTP routes: `apps/api/issuebot/routes.py`
- DocsGPT parsing: `apps/api/issuebot/docsgpt.py` and `report.py`
- GitHub calls: `apps/api/issuebot/github.py`
- Webhook decisions: `apps/api/issuebot/webhook.py`
- Job claim and retries: `apps/api/issuebot/worker.py`
- Pages: `apps/web/src/pages`

A new route that changes state must depend on `require_user` and the CSRF dependency already applied to the authenticated router. Do not log secrets. Add a test that uses the httpx mock transport in `tests/conftest.py`.

## Debugging

Logs are JSON. The redaction formatter strips known secret shapes. Set `ISSUEBOT_LOG_LEVEL=DEBUG` locally. Readiness is `GET /api/health/live` and `GET /api/health/ready`. Ready returns 503 when the database is down or the worker heartbeat is older than 30 seconds. A disabled worker is reported as disabled and still ready.
