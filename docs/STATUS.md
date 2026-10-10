# Status

Last updated 2026-10-10.

## Implemented

- GitHub webhook endpoint with raw-body HMAC-SHA256 verification, unique delivery ids, a 1 MB limit, an allowlist (empty denies), and installation lifecycle tracking.
- Durable jobs in the database, an in-process worker, a 10-minute lease, automatic retries for transient errors (default 5 attempts), and manual retry (limit 3).
- DocsGPT client for `POST /api/answer` with `api_key` in the body, no redirects, an outbound URL policy, and transient retry. Pending tool calls fail the job.
- Evidence report: documented facts, historical evidence, hypotheses, unknowns, next steps, questions, sources, related issues, and limitations. Facts are demoted to unknowns when DocsGPT returns no sources. Model-written URLs are not sources.
- GitHub App JWT, downscoped installation tokens kept in memory, issue fetch, related-issue search with an honest failure note, and comment creation.
- Publishing: off by default, blocked in demo mode, requires a session, CSRF header, acknowledgement, and matching content hash. One publish row per investigation, with a marker lookup before POST. Mentions are neutralized. The comment lists DocsGPT sources only.
- One local admin with scrypt passwords, a 12-hour cookie session, CSRF header, lockout after 5 failures, and password change.
- Settings stored with Fernet. The API returns configured flags, never values.
- Dashboard pages: sign-in, overview, investigations with search and filters (repository, status, issue number, dates) and pagination, investigation detail with comment review, settings with installation status and connection tests, health, and password change.
- Demo mode with fixtures, a seeded sample issue, and a banner.
- Docker Compose (Postgres on the internal network only, web on `127.0.0.1:8080`), non-root API image, unprivileged nginx image, health checks, CI workflow, issue and PR templates.

## Checks run on 2026-10-10

| Check | Result |
| --- | --- |
| `pytest -q` in `apps/api` (Python 3.14.7 venv) | 20 passed, about 70% line coverage |
| `ruff check issuebot tests` | passed |
| `ruff format --check issuebot tests` | passed |
| `mypy issuebot` | passed, 18 files |
| `npm test` in `apps/web` (Vitest) | 6 passed |
| `npm run lint` | passed |
| `npm run build` (tsc and Vite) | passed |
| `docker compose config` with `.env.example` copied to `.env` | passed |
| Secret pattern grep from the CI workflow | no matches outside tests |
| `npm audit` | first run: 3 findings, all in the dev-only Vitest 3 chain. After upgrading to Vitest 5: 0 findings, tests still pass |
| `pip-audit --skip-editable` in the API venv | no known vulnerabilities |
| `docker build` for both images, locally | not run. The Docker daemon was not running |
| GitHub Actions run [38059776184](https://github.com/j4b3-21/IssueBot/actions/runs/38059776184) | passed: api, web, docker (compose config and both image builds), secrets. This run predates the changes below |
| Demo mode in a browser against the real API and SQLite | sign-in, overview, detail, comment preview, blocked publish, settings without secret values, refused secret save without a Fernet key, and health all checked by hand |

Found and fixed during the browser check: Alembic's `fileConfig` replaced the redacting log handler and silenced uvicorn startup logs. A regression test now covers it.

## Not run or not verified

- The Compose stack has not been started, so the `SKIP LOCKED` claim path has not run against PostgreSQL. Tests and the demo used SQLite. The images were built in CI only.
- Live DocsGPT. No API key was available. The request shape follows the docs checked on 2026-10-10. Tests use mocked HTTP.
- Live GitHub. No App credentials were available. JWT, token exchange, issue fetch, search, and comment creation are exercised only against mocked HTTP.
- Local tests were run on Python 3.14. CI runs them on Python 3.12, which the image uses.
- Phone-width layout was not visually confirmed. The browser tool returned stale screenshots after a viewport change.
- No Playwright end-to-end test. The browser check above was manual.
- Audits are not part of CI yet.

## Known limitations

- DocsGPT does not cite per sentence. Sources apply to the whole answer.
- GitHub Search permission for GitHub Apps is not documented clearly. Search failures are recorded and do not fail the job.
- Prompt-injection defenses reduce risk and do not eliminate it.
- One administrator. No roles.
- A job whose lease expires can call DocsGPT twice. Comments are still protected by the marker and the unique publish row.
- No automatic retention. Delivery ids are kept forever.
- No license file. Ownership has not been decided.

## Next steps

1. Start Docker and run `docker compose up --build`, then check the Postgres claim path.
2. Create a test GitHub App and a DocsGPT agent, use the connection tests, and send one real `issues.opened` delivery to an allowlisted repository. Record the result here.
3. Add a Playwright test for the demo flow.
4. Add `pip-audit` and `npm audit` to CI.
5. Choose a license.
