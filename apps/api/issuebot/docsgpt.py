"""DocsGPT agent client.

Verified 2026-10-10 against https://docs.docsgpt.cloud/API/agent-api.
The agent is selected by `api_key` in the JSON body of POST /api/answer.
Sources are taken only from the documented `sources` array.
"""

from __future__ import annotations

import logging
import socket
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from issuebot.errors import TRANSIENT_CODES, IntegrationError
from issuebot.runtime import RuntimeConfig
from issuebot.safety import UnsafeURL, assess_url
from issuebot.settings import Settings

log = logging.getLogger("issuebot.docsgpt")

DEMO_ANSWER = """{
  "summary": "Demo fixture: the widget stays blank when the page loads.",
  "documented_facts": [{"text": "The demo source says the API key is read from the environment."}],
  "hypotheses": ["The API key may be missing in this environment."],
  "unknowns": ["Which browser and version reproduced the blank page."],
  "next_steps": ["Open the browser console and confirm whether the API request is sent."],
  "questions_for_reporter": ["Which version of the project is deployed?"],
  "limitations": ["This is a demo fixture, not a live DocsGPT answer."]
}"""


@dataclass
class DocsGPTResult:
    answer: str
    sources: list[dict]
    conversation_id: str | None
    structured: dict | None
    correlation_id: str
    mock: bool = False
    raw_keys: list[str] = field(default_factory=list)


class DocsGPTClient:
    def __init__(
        self,
        config: RuntimeConfig,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper=time.sleep,
        resolver=socket.getaddrinfo,
    ) -> None:
        self.config = config
        self.settings = settings
        self.sleeper = sleeper
        self.resolver = resolver
        timeout = httpx.Timeout(settings.http_read_timeout, connect=settings.http_connect_timeout)
        self.http = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)

    def close(self) -> None:
        self.http.close()

    def answer(self, question: str) -> DocsGPTResult:
        correlation_id = str(uuid.uuid4())
        if self.config.demo_mode:
            log.info("docsgpt demo response correlation=%s", correlation_id)
            return DocsGPTResult(
                answer=DEMO_ANSWER,
                sources=[
                    {
                        "title": "Demo source (fixture, not a live document)",
                        "source": "https://example.com/issuebot-demo-source",
                        "text": "The demo knowledge base says the API key is read from the environment.",
                    }
                ],
                conversation_id="demo-conversation",
                structured=None,
                correlation_id=correlation_id,
                mock=True,
                raw_keys=["answer", "sources", "conversation_id"],
            )
        if not self.config.docsgpt_base_url or not self.config.docsgpt_api_key:
            raise IntegrationError("config_missing")
        url = _answer_url(self.config.docsgpt_base_url)
        self._guard(url)
        log.info("docsgpt request correlation=%s", correlation_id)
        response = self._send(url, question)
        log.info("docsgpt response correlation=%s status=%s", correlation_id, response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise IntegrationError("docsgpt_bad_response") from exc
        if not isinstance(payload, dict):
            raise IntegrationError("docsgpt_bad_response")
        if payload.get("pending_tool_calls"):
            raise IntegrationError("docsgpt_paused")
        answer = payload.get("answer")
        if not isinstance(answer, str):
            raise IntegrationError("docsgpt_bad_response")
        sources = payload.get("sources")
        if not isinstance(sources, list):
            sources = []
        structured = (
            payload.get("structured") if isinstance(payload.get("structured"), dict) else None
        )
        conversation_id = payload.get("conversation_id")
        return DocsGPTResult(
            answer=answer,
            sources=[item for item in sources if isinstance(item, dict)],
            conversation_id=conversation_id if isinstance(conversation_id, str) else None,
            structured=structured,
            correlation_id=correlation_id,
            mock=False,
            raw_keys=sorted(str(key) for key in payload.keys()),
        )

    def _guard(self, url: str) -> None:
        try:
            assess_url(
                url,
                production=self.settings.production,
                allow_private=self.settings.allow_private_docsgpt,
                resolver=self.resolver,
            )
        except UnsafeURL as exc:
            if exc.code == "unresolvable":
                raise IntegrationError("docsgpt_network") from exc
            raise IntegrationError("docsgpt_unsafe_url") from exc

    def _send(self, url: str, question: str) -> httpx.Response:
        attempts = self.settings.http_retries + 1
        last: IntegrationError | None = None
        for attempt in range(attempts):
            try:
                response = self.http.post(
                    url,
                    json={"question": question, "api_key": self.config.docsgpt_api_key},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
            except httpx.TimeoutException as exc:
                last = IntegrationError("docsgpt_timeout")
                last.__cause__ = exc
            except httpx.TransportError as exc:
                last = IntegrationError("docsgpt_network")
                last.__cause__ = exc
            else:
                if response.status_code in {301, 302, 303, 307, 308}:
                    raise IntegrationError("docsgpt_redirect")
                try:
                    _raise_for_status("docsgpt", response)
                except IntegrationError as exc:
                    if exc.code not in TRANSIENT_CODES:
                        raise
                    last = exc
                else:
                    return response
            if attempt + 1 < attempts and last is not None:
                self.sleeper(_delay(last, attempt))
        assert last is not None
        raise last


def _answer_url(base: str) -> str:
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or parsed.path not in {"", "/"}:
        raise IntegrationError("docsgpt_bad_config")
    return base.rstrip("/") + "/api/answer"


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after", "")
    if header.isdigit():
        return float(header)
    return None


def _rate_limited(response: httpx.Response) -> bool:
    if response.headers.get("x-ratelimit-remaining") == "0":
        return True
    snippet = response.text[:300].lower()
    return "rate limit" in snippet or "quota" in snippet


def _raise_for_status(prefix: str, response: httpx.Response) -> None:
    code = response.status_code
    if code < 400:
        return
    retry_after = _retry_after(response)
    if code == 429 or (code == 403 and _rate_limited(response)):
        raise IntegrationError(f"{prefix}_rate_limit", retry_after=retry_after)
    if code in {401, 403} and prefix == "docsgpt":
        raise IntegrationError("docsgpt_auth")
    if code == 401:
        raise IntegrationError(f"{prefix}_auth")
    if code == 403:
        raise IntegrationError(f"{prefix}_forbidden")
    if code == 404:
        raise IntegrationError(f"{prefix}_not_found")
    if code >= 500 or code == 408:
        raise IntegrationError(f"{prefix}_unavailable", retry_after=retry_after)
    raise IntegrationError(f"{prefix}_bad_response")


def _delay(error: IntegrationError, attempt: int) -> float:
    if error.retry_after is not None:
        # ponytail: cap so one in-process worker cannot sleep for a full hour window.
        return min(error.retry_after, 60.0)
    return min(0.5 * (2**attempt), 8.0)
