# Operations

## Backup

Postgres is the only durable store.

```bash
docker compose exec postgres pg_dump -U issuebot issuebot > issuebot.sql
```

Restore into an empty database after stopping the API:

```bash
docker compose stop api web
docker compose exec -T postgres psql -U issuebot -d issuebot < issuebot.sql
docker compose start api web
```

The dump contains issue text and encrypted secrets. Store it with the same care as the Fernet key. Without the key, ciphertext in the dump cannot be decrypted.

## Upgrade

Pull the new revision, rebuild, and start one API container. It runs `alembic upgrade head` before it serves traffic. Read the migration before deploying. There is no online downgrade script. Take a backup first.

## Health

`GET /api/health/live` for process up. `GET /api/health/ready` for database and worker heartbeat. Compose marks the API healthy from the live check. The signed-in Health page adds dependency configuration without credentials.

## Logs

Stdout is JSON. The formatter redacts values that look like tokens, PEM blocks, and webhook signatures. Ship logs to a system that is not world-readable. Do not enable a reverse proxy that logs `Authorization` or cookie headers.

## Retention

Nothing expires automatically. Delete an investigation in the API when you do not want the issue snapshot. Delivery ids remain so GitHub redelivery stays idempotent. To wipe an environment, stop Compose and remove the volume named by `docker volume ls`. That is destructive.

## Publishing

Turn the switch off in Settings to stop new comments. In-flight publish requests that already passed the check can still finish. Demo mode forces the switch off. To stop investigations entirely, set `ISSUEBOT_WORKER_ENABLED=false` and restart. Webhooks are still stored.

## Recovery

A failed job stays failed until a maintainer retries it, within the manual limit. A publish that crashed after GitHub accepted the comment is recovered by searching for the `issuebot:{uuid}` marker before creating another comment. Restarting the API resumes queued jobs. A job left in `running` past its lease can be claimed again, so DocsGPT may be called twice. Comment creation is still guarded by the marker and the unique publish row.

## TLS

Terminate TLS at a proxy that forwards to `127.0.0.1:8080`. Set `ISSUEBOT_PUBLIC_BASE_URL` to the `https` origin so the session cookie is Secure and the webhook URL matches GitHub.
