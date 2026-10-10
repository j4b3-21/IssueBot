# Implementation plan

The product name is IssueBot. The original build notes used another name. Code, UI, and docs use IssueBot.

## Decisions

1. One FastAPI process and PostgreSQL. Jobs use row locks. Redis was not added.
2. DocsGPT is `POST {origin}/api/answer` with `api_key` in the JSON body. Checked 2026-10-10.
3. GitHub App JWT and installation tokens follow the REST docs checked the same day. API version header `2026-03-10`.
4. SQLite is the test database. Production and Compose use PostgreSQL. JSON columns stay portable.
5. One bootstrap administrator, scrypt passwords, cookie session, CSRF header.
6. Secrets at rest use Fernet. The API returns configured flags only.
7. Publishing defaults off and is impossible in demo mode.
8. The dashboard is React, TypeScript, and Vite with Tailwind. Data fetching is `fetch`.

## Phases

| Phase | Result |
| --- | --- |
| 0 | API contracts checked and recorded in the client modules and `docs/architecture.md` |
| 1 | Package layout, Compose, CI, env example |
| 2 | Models, Alembic, settings, auth |
| 3 | DocsGPT client and report shaping |
| 4 | Webhook HMAC, delivery id, allowlist, installation events |
| 5 | Worker, evidence report, retries |
| 6 | Dashboard routes |
| 7 | Comment preview and explicit publish |
| 8 | GitHub issue search with an honest failure |
| 9 | Tests, docs, and the status page |

## Out of scope

Multi-user RBAC, Redis, automatic comments, per-sentence citations, and a chosen open-source license.
