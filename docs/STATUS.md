# Status

Last updated 2026-10-10.

## Implemented

- Webhook intake: HMAC-SHA256 over the raw body, unique delivery id, 1 MB limit, allowlist (empty denies), installation lifecycle events.
- Durable jobs in the database, in-process worker, lease recovery, bounded automatic retries, manual retry limit.
- DocsGPT client for `POST /api/answer` with `api_key` in the body. No redirects. Paused tool calls fail the job.
- Evidence report: documented facts only when DocsGPT returned sources, otherwise demoted to unknowns. Sources only from the `sources` array.
- GitHub App JWT, downscoped installation tokens in memory, issue fetch, related-issue search with an honest failure note.
- Comment preview, acknowledgement plus content hash, kill switch, allowlist and installation checks, marker lookup before create, `@` neutralized.
- One bootstrap admin, scrypt, cookie session, CSRF header, login lockout, password change.
- Settings with Fernet-encrypted secrets and configured flags only.
- Dashboard: sign-in, overview, filtered and paginated list, detail with fact, hypothesis, and unknown rails, sources, related issues, timeline, retry, publish panel, settings, health.
- Demo mode with fixtures. Publishing is blocked.
- Dockerfiles, Compose, CI workflow, issue and PR templates.

## Checks run

| Check | Result |
| --- | --- |
| `pytest -q` in `apps/api` | 18 passed, coverage 70% |
| `ruff check` and `ruff format --check` | passed |
| `mypy issuebot` | no issues in 18 files |
| `npm test` in `apps/web` | 6 passed |
| `npm run lint` | passed |
| `tsc --noEmit` and `vite build` | passed |
| `docker compose config` | passed with `.env` copied from `.env.example` |
| Secret pattern grep, excluding test fixtures | no match |
| `docker build` for both images | not run. The Docker daemon was not running |
| CI workflow on GitHub | not run yet |

## Live integrations

- DocsGPT: not called with a real key. The contract was checked against the docs on 2026-10-10. Tests use mocked HTTP.
- GitHub: not called with a real App. The contract was checked against the docs on 2026-10-10. Tests use mocked HTTP.
- GitHub Search permission for an App token is unconfirmed. The worker records a failure and continues.

## Known gaps

- The dashboard was not exercised end to end in a browser in this session.
- No Playwright test.
- Startup migrations assume a single API process.
- No automatic data retention job.
- No license selected.

## Next steps

1. Start Docker and run `docker compose up --build`, then sign in and load the demo sample.
2. Configure a real DocsGPT agent and use Test DocsGPT.
3. Create a GitHub App on a test repository, send an `issues.opened` webhook, and approve one comment.
4. Add a browser test for sign-in, detail, and publish blocked in demo mode.
