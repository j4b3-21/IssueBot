.PHONY: test lint typecheck demo up

PY ?= .venv/bin

test:
	cd apps/api && ../../$(PY)/pytest -q
	cd apps/web && npm test

lint:
	cd apps/api && ../../$(PY)/ruff check issuebot tests
	cd apps/web && npm run lint

typecheck:
	cd apps/api && ../../$(PY)/mypy issuebot
	cd apps/web && npx tsc --noEmit

demo:
	ISSUEBOT_IGNORE_ENV_FILE=1 ISSUEBOT_DEMO_MODE=1 ISSUEBOT_ENV=development \
	ISSUEBOT_DATABASE_URL=sqlite:///./issuebot-demo.db \
	ISSUEBOT_PUBLIC_BASE_URL=http://127.0.0.1:8000 \
	ISSUEBOT_ADMIN_PASSWORD=$${ISSUEBOT_ADMIN_PASSWORD:-change-me-demo} \
	ISSUEBOT_FERNET_KEY=$${ISSUEBOT_FERNET_KEY:-} \
	$(PY)/uvicorn issuebot.main:app --app-dir apps/api --host 127.0.0.1 --port 8000

up:
	docker compose up --build
