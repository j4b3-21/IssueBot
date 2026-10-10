# Troubleshooting

Messages below are the ones the API returns. They do not include tokens.

## DocsGPT

| Code | What to check |
| --- | --- |
| `docsgpt_auth` | The API key in Settings. The key selects the agent |
| `docsgpt_bad_config` | Base URL must be an origin with no path |
| `docsgpt_unsafe_url` | Production blocks private and `http` URLs unless private access is enabled |
| `docsgpt_timeout` / `docsgpt_unavailable` | DocsGPT is up and the read timeout is long enough for the agent |
| `docsgpt_paused` | The agent asked for tool approval. Turn that off in DocsGPT or use an agent that answers directly |
| `docsgpt_redirect` | Point at the final origin. Redirects are ignored on purpose |
| `docsgpt_bad_response` | The body was not the documented JSON shape |

An agent id in Settings is a label. A wrong id does not change the request. A wrong API key does.

## GitHub

| Code | What to check |
| --- | --- |
| `github_auth` | App id and PEM. Test GitHub calls `GET /app` |
| `github_forbidden` | The App is installed on that repository and has Issues permission |
| `github_not_found` | Issue number and repository |
| `github_rate_limit` | Wait and use the manual retry. The report's search note may mention search limits without failing the job |
| `installation_inactive` | The installation webhook marked it suspended or deleted |
| `repo_not_allowed` | Allowlist is exact `owner/name` |

A bad webhook signature returns 401. An empty webhook secret returns 401 for every delivery. A duplicate `X-GitHub-Delivery` returns 202 and does not create a second job.

## Jobs

Queued with no progress: the worker is disabled, or readiness shows `worker: stale` because the process is wedged. Restart the API. A running job older than the 10-minute lease can be claimed again.

Failed with `config_missing`: DocsGPT or GitHub settings are incomplete and demo mode is off.

Failed with a transient code: automatic retries stop at `ISSUEBOT_JOB_MAX_ATTEMPTS`. Use Retry on the detail page. The manual limit is 3.

## Database

Startup fails if Postgres is down or the URL is wrong. Compose waits for `pg_isready`. A migration error is in the API logs. Do not delete the volume to clear a migration error until you have a backup.

SQLite demo file `issuebot-demo.db` is local only. Delete that file to reset a demo database. That removes the admin user, so the next start recreates it from `ISSUEBOT_ADMIN_PASSWORD`.

## Publish

`publish_blocked` includes the reason: demo mode, switch off, allowlist, inactive installation, or an unfinished investigation. `stale_preview` means the report changed. Refresh and approve the new hash. `publish_in_progress` means another request holds the row. Wait and reload.

## Diagnostics

Copy the investigation id, status, `error_code`, and the JSON log line. Remove any header that looks like a token before sharing it. The log redactor is a backstop, not a review step.
