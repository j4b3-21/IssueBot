# Contributing

## Setup

Follow [docs/development.md](docs/development.md). Run `make test` and `make lint` before a pull request.

## Branches and commits

Use a short branch name. Commit messages should say why the change exists. Do not commit `.env`, PEM files, or database files.

## Tests

Backend tests live in `apps/api/tests` and mock DocsGPT and GitHub. Frontend tests live in `apps/web/src/ui.test.tsx`. Add a test when you change webhook verification, publishing, source handling, or authentication.

## Bug reports

Use the Bug issue template. Include the error code and a redacted log. Do not paste secrets.

## Features

Open a Feature issue with the problem, the proposed behavior, and whether webhooks, secrets, publishing, or outbound HTTP change. Publishing must stay behind an explicit human approval.

## Security-sensitive changes

Call out signature verification, CSRF, URL checks, token scope, and comment rendering in the pull request. Do not weaken a check to make a demo pass. Report vulnerabilities as described in [SECURITY.md](SECURITY.md).
