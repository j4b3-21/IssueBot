"""Safe error codes. Exception text is never returned to clients."""

from __future__ import annotations

from fastapi import HTTPException

ERROR_MESSAGES = {
    "docsgpt_auth": "DocsGPT rejected the API key.",
    "docsgpt_timeout": "DocsGPT did not respond in time.",
    "docsgpt_rate_limit": "DocsGPT rate limit was reached.",
    "docsgpt_unavailable": "DocsGPT was unavailable.",
    "docsgpt_network": "DocsGPT could not be reached.",
    "docsgpt_bad_response": "DocsGPT returned a response IssueBot could not use.",
    "docsgpt_redirect": "DocsGPT redirected the request. Redirects are not followed.",
    "docsgpt_unsafe_url": "The DocsGPT URL is not allowed by the outbound policy.",
    "docsgpt_paused": "The DocsGPT agent paused for tool approval. IssueBot does not approve tools.",
    "docsgpt_bad_config": "The DocsGPT base URL must be an origin without a path.",
    "github_auth": "GitHub rejected the app credentials.",
    "github_forbidden": "GitHub refused access. Check the app installation and permissions.",
    "github_not_found": "The GitHub issue was not found.",
    "github_rate_limit": "GitHub rate limit was reached.",
    "github_unavailable": "GitHub was unavailable.",
    "github_network": "GitHub could not be reached.",
    "github_timeout": "GitHub did not respond in time.",
    "github_bad_response": "GitHub returned a response IssueBot could not use.",
    "github_unsafe_url": "The GitHub URL is not allowed by the outbound policy.",
    "config_missing": "DocsGPT or GitHub settings are incomplete.",
    "installation_inactive": "The GitHub App installation is suspended or deleted.",
    "repo_not_allowed": "The repository is not on the allowlist.",
    "unknown": "The investigation failed.",
}

TRANSIENT_CODES = {
    "docsgpt_timeout",
    "docsgpt_rate_limit",
    "docsgpt_unavailable",
    "docsgpt_network",
    "github_timeout",
    "github_rate_limit",
    "github_unavailable",
    "github_network",
    "unknown",
}


class IntegrationError(Exception):
    def __init__(self, code: str, retry_after: float | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def safe_message(code: str) -> str:
    return ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "message": message})
