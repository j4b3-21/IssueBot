# Configuration

Settings load from the environment. Names use the prefix `ISSUEBOT_`. A `.env` file in the project or a parent directory is read unless `ISSUEBOT_IGNORE_ENV_FILE=1`. Values saved in Settings override the environment for DocsGPT, the GitHub App id, the private key, the webhook secret, the allowlist, and the publish switch. Secrets in the database are Fernet ciphertext and are never returned by the API.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `ISSUEBOT_ENV` | no | `development` | `development` or `production` |
| `ISSUEBOT_DATABASE_URL` | yes in practice | local Postgres URL | SQLAlchemy URL. Compose overrides this to the `postgres` service |
| `ISSUEBOT_DB_PASSWORD` | for Compose | `change-me` | Postgres password. Keep it aligned with the database URL |
| `ISSUEBOT_PUBLIC_BASE_URL` | no | `http://localhost:8080` | Public origin. Used for CORS, the webhook URL, and the Secure cookie flag |
| `ISSUEBOT_ADMIN_USERNAME` | no | `admin` | First user, created only when the users table is empty |
| `ISSUEBOT_ADMIN_PASSWORD` | yes on first boot | empty | At least 12 characters. Not used after the user exists |
| `ISSUEBOT_FERNET_KEY` | to save secrets | empty | Fernet key. Required before Settings can store a secret |
| `ISSUEBOT_DOCSGPT_BASE_URL` | for live runs | empty | Origin only, such as `https://gptcloud.arc53.com` |
| `ISSUEBOT_DOCSGPT_API_KEY` | for live runs | empty | Agent API key |
| `ISSUEBOT_DOCSGPT_AGENT_ID` | no | empty | Display label. Not sent with the key |
| `ISSUEBOT_GITHUB_APP_ID` | for live GitHub | empty | Numeric App id |
| `ISSUEBOT_GITHUB_PRIVATE_KEY` | one of key or path | empty | PEM contents |
| `ISSUEBOT_GITHUB_PRIVATE_KEY_PATH` | one of key or path | empty | Path to a PEM file that is not in git |
| `ISSUEBOT_GITHUB_WEBHOOK_SECRET` | for webhooks | empty | HMAC secret. Empty rejects every webhook |
| `ISSUEBOT_ALLOWED_REPOS` | no | empty | Comma-separated `owner/name`. Empty denies all |
| `ISSUEBOT_MAX_ISSUE_CHARS` | no | `12000` | Issue body stored and sent, 500–100000 |
| `ISSUEBOT_JOB_MAX_ATTEMPTS` | no | `5` | Automatic attempts, 1–20 |
| `ISSUEBOT_MANUAL_RETRY_LIMIT` | no | `3` | Maintainer retries of a failed job |
| `ISSUEBOT_HTTP_CONNECT_TIMEOUT` | no | `5` | Seconds |
| `ISSUEBOT_HTTP_READ_TIMEOUT` | no | `60` | Seconds |
| `ISSUEBOT_HTTP_RETRIES` | no | `2` | Retries for transient GET-style calls. Comments are not retried |
| `ISSUEBOT_LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `ISSUEBOT_DEMO_MODE` | no | `false` | Fixtures only. Publishing stays off |
| `ISSUEBOT_WORKER_ENABLED` | no | `true` | Set false to accept webhooks without processing |
| `ISSUEBOT_ALLOW_PRIVATE_DOCSGPT` | no | `false` | Allow private and loopback DocsGPT addresses |
| `ISSUEBOT_PUBLISH_ENABLED` | no | `false` | Initial publish switch. Demo mode still forces it off |

## Production

Set `ISSUEBOT_ENV=production`, an `https` public URL, a long admin password, a Fernet key, and a webhook secret. Leave private DocsGPT access off unless DocsGPT is on a trusted network and you accept that exception. Put TLS in front of the web container. Do not publish Postgres.

## DocsGPT

The base URL is an origin. IssueBot appends `/api/answer`. The API key is the agent credential described in the [Agent API](https://docs.docsgpt.cloud/API/agent-api). Find the key in the DocsGPT agent settings. Saving a blank secret field keeps the current secret.

## GitHub App

Webhook URL shown in Settings is `{public base}/api/v1/webhooks/github`. Permissions: Issues read and write. Events: Issues, Installation. The private key PEM must contain `PRIVATE KEY`.

## Rotation

1. Generate a new Fernet key only when you can re-enter every secret. Old ciphertext cannot be read with a new key.
2. Rotate the webhook secret in GitHub and IssueBot together. Deliveries signed with the old secret fail closed.
3. Generate a new GitHub App private key, save it, then delete the old key in GitHub.
4. Replace the DocsGPT API key in the agent UI and in Settings.
5. Change the admin password in Settings. That does not reveal the old password.

Restart the API after changing environment variables. Settings saved in the database apply on the next request without a restart.
