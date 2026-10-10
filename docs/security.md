# Security

IssueBot holds private issue text and a key that can read a documentation agent. Treat the host like a production admin tool.

## Threat model

An attacker may send a forged webhook, replay a delivery, put instructions in an issue, or trick a maintainer into publishing a comment that mentions someone. A stolen admin cookie could change settings or publish. A stolen DocsGPT key could query the knowledge base. A stolen GitHub private key could mint installation tokens.

IssueBot does not try to be a multi-tenant SaaS boundary. One administrator is trusted with the data the app stores.

## Prompt injection

Issue text is wrapped in `<untrusted_issue>` and the prompt says not to follow instructions inside it. The worker does not execute tools requested by the issue or by the model. `pending_tool_calls` fails the job. The public comment is built from the structured report fields, escaped, and not from raw model Markdown. This reduces the chance that an issue controls a GitHub comment. It does not make the model immune to instruction text.

## Secrets

Environment and database secrets are not included in API responses. Settings returns `configured` booleans. Logs pass through a redactor. Installation tokens live in process memory and are dropped after publish. Do not commit `.env` or PEM files.

## Webhooks

The signature is checked before the JSON is trusted. The comparison is `hmac.compare_digest`. An empty secret rejects every delivery. The delivery id is a primary key, so a replay does not create a second investigation. Bodies over 1 MB are rejected.

## Sessions

The session cookie is HttpOnly and SameSite=Lax, and Secure on HTTPS public URLs. Five failed logins lock the account for 15 minutes. The sixth attempt is rejected even if the password is then correct. State-changing routes require `X-IssueBot-Request: 1`, so a cross-site form cannot publish. Passwords are stored with stdlib scrypt.

## Outbound HTTP

DocsGPT and GitHub URLs are checked before the client connects. Link-local, multicast, reserved, and unspecified addresses are blocked. Private and loopback addresses are blocked in production unless `ISSUEBOT_ALLOW_PRIVATE_DOCSGPT` is set, and that flag does not apply to GitHub. Redirects are not followed. Source links in the UI are rendered only when the server marked them linkable, which requires `https` and a public host.

## GitHub permissions

The App should have Issues read and write. Metadata is implicit. Tokens are downscoped to Issues and, when a repository id is known, to that repository. Contents and pull request permissions are not requested. Search can fail closed when the token cannot search. Comments are created only after a person acknowledges a hash of the exact body.

## Retention and deletion

Deleting an investigation removes that row and its jobs. Webhook delivery ids are kept so a redelivery stays idempotent. There is no automatic retention job. Back up the database if you need the history, and delete the volume when you do not. See [operations](operations.md).

## Reporting

See [SECURITY.md](../SECURITY.md).

## Known limits

Signature verification does not expire a delivery by timestamp beyond GitHub's own retry behavior. The unique delivery id is the replay control. A maintainer who approves a misleading comment will still publish it. Demo mode must not be used as an access-control boundary on a public URL, because the demo admin password is whatever you configured.
