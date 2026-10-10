# Agent notes

## Layout

- `apps/api/issuebot` — FastAPI app, worker, DocsGPT and GitHub clients
- `apps/api/tests` — pytest, SQLite, mocked HTTP
- `apps/web` — React dashboard
- `docs` — behavior that must match the code
- `infra/docker` — API and nginx images

## Commands

```bash
.venv/bin/pytest -q
```

from `apps/api`, and `npm test`, `npm run lint`, `npm run build` from `apps/web`. `make test` runs both suites when the venv and `node_modules` exist.

## Constraints

- Verify DocsGPT and GitHub docs again before changing request shapes. The clients record the check date in their module docstrings.
- Do not auto-publish GitHub comments. Approval, content hash, allowlist, installation status, and the kill switch all stay.
- Do not return secrets to the browser or write them into logs, audits, or docs.
- Do not store installation tokens.
- Do not follow redirects on outbound calls.
- Do not add a source URL that DocsGPT did not return.
- Empty repository allowlist means deny.
- Demo mode never publishes.
- Keep one API process. Migrations run on startup.
- Prefer the standard library and the existing stack. No Redis unless a measured need appears.

## After a change

Update the docs that describe the behavior and `docs/STATUS.md` with the checks you actually ran. Do not claim a live DocsGPT or GitHub call worked unless you made one.
