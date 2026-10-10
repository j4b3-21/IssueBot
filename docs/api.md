# HTTP API

Interactive docs are served by the API at `/docs` and `/redoc`. Through Compose they are available at `http://127.0.0.1:8080/docs` because nginx proxies them. Examples below use no real secrets.

Authenticated routes need the `issuebot_session` cookie. Mutations also need `X-IssueBot-Request: 1`. Errors look like `{"error":"code","message":"safe text"}`. Validation errors add `fields` and do not echo the submitted values.

## Health

`GET /api/health/live` → `{"status":"live"}`.

`GET /api/health/ready` → `{"status":"ok","database":"ok","worker":"ok"}`. Worker `disabled` is still ok. A stale worker or a database error returns 503.

`GET /api/v1/health` requires a session and adds DocsGPT and GitHub configuration states: `configured`, `not_configured`, or `demo`.

## Session

`POST /api/v1/auth/login` with `{username, password}`. 401 on failure, 429 when locked.

`POST /api/v1/auth/logout`.

`GET /api/v1/auth/me` → `{username, demo_mode}`.

`POST /api/v1/account/password` with `{current_password, new_password}`. The new password must be at least 12 characters.

## Investigations

`GET /api/v1/overview` → counts, up to 8 recent rows, and up to 8 failed rows.

`GET /api/v1/investigations` query: `repo`, `status`, `issue_number`, `q`, `created_from`, `created_to`, `limit` (1–50), `offset`. Status may be `queued`, `running`, `completed`, `failed`, `awaiting_approval`, or `comment_published`.

`GET /api/v1/investigations/{id}` returns the summary, issue snapshot, report, audit events, comment preview, publish block reason, and retry permission.

`POST /api/v1/investigations/{id}/retry` queues a failed investigation again.

`DELETE /api/v1/investigations/{id}` deletes that investigation.

`POST /api/v1/investigations/{id}/comment-preview` returns the body and `content_sha256`.

`POST /api/v1/investigations/{id}/publish-comment` with `{acknowledged: true, content_sha256}`. The hash must match the current preview. 409 covers a disabled switch, demo mode, a stale hash, an inactive installation, or a removed repository.

## Settings

`GET /api/v1/settings` returns URLs, allowlist, publish flags, installation account and status, and booleans such as `docsgpt_api_key_configured`. It does not return secret values.

`PUT /api/v1/settings` updates the fields you send. An empty secret string keeps the stored secret.

`POST /api/v1/settings/test-docsgpt` and `POST /api/v1/settings/test-github` return `{ok, message}` and, for DocsGPT, a source count. Failures use the safe error text.

## Webhook

`POST /api/v1/webhooks/github` with the raw body and `X-Hub-Signature-256`. No session. A duplicate delivery returns 202 with an idempotent body. `issues` / `opened` on an allowlisted repository creates a job. Other events are stored and ignored, except installation lifecycle events, which update installation status.

## Demo

`POST /api/v1/demo/sample-issue` exists only when demo mode is on. It queues the fixture issue `acme/widget`.
