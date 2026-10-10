# Security policy

IssueBot is a self-hosted maintainer tool. If you find a vulnerability, open a private GitHub security advisory on the repository that hosts your fork or deployment, or email the maintainers of that deployment. Do not include live API keys, private keys, or webhook secrets in the report. Describe the version, the request path, and the impact.

This tree does not yet name a security contact because ownership of the public repository has not been set. Until it is, report issues to the person who operates your instance.

## What to include

- The IssueBot version or git revision.
- Whether demo mode and publishing were enabled.
- The HTTP status and the `error` code. Omit upstream response bodies if they might contain source text.

## Supported expectations

Webhook signatures, delivery deduplication, secret redaction, and human approval before comments are in scope. Complete prevention of prompt injection is not claimed. See [docs/security.md](docs/security.md).
