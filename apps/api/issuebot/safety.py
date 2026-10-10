"""Redaction, password hashing, URL policy, and untrusted-text handling."""

from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import re
import secrets
from urllib.parse import urlparse

_REDACTIONS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghs_[A-Za-z0-9]+"),
    re.compile(
        r"(?i)(api_key|webhook_secret|password|token|secret)(\s*[:=]\s*)(\S+)",
    ),
]
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


class UnsafeURL(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def redact(text: str) -> str:
    cleaned = text
    for pattern in _REDACTIONS:
        if pattern.groups >= 3:
            cleaned = pattern.sub(r"\1\2[redacted]", cleaned)
        else:
            cleaned = pattern.sub("[redacted]", cleaned)
    return cleaned


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return hmac.compare_digest(derived.hex(), hash_hex)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def github_signature_matches(secret: str, body: bytes, header: str) -> bool:
    """Compare the raw-body HMAC-SHA256 to X-Hub-Signature-256."""
    if not secret or not header:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    presented = header
    if presented.lower().startswith("sha256="):
        presented = "sha256=" + presented.split("=", 1)[1].strip().lower()
    if len(presented) != len(expected):
        return False
    return hmac.compare_digest(expected, presented)


def plain_text(value: str | None, limit: int) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def neutralize_mentions(text: str) -> str:
    """Break @mentions copied from untrusted text so GitHub does not notify them."""
    return re.sub(r"@", "@\u200b", text)


def parse_repo_list(value: str) -> list[str]:
    repos: list[str] = []
    for part in value.split(","):
        repo = part.strip()
        if not repo:
            continue
        if not _REPO_RE.fullmatch(repo):
            raise ValueError(f"invalid repository: {repo}")
        repos.append(repo)
    return repos


def valid_repo_name(value: str) -> bool:
    return bool(_REPO_RE.fullmatch(value))


def _ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_private: bool) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_blocked(mapped, allow_private=allow_private)
    if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if (ip.is_private or ip.is_loopback) and not allow_private:
        return True
    return False


def assess_url(
    url: str,
    *,
    production: bool,
    allow_private: bool,
    resolver,
) -> None:
    """Reject destinations that are not an intentional DocsGPT or GitHub host.

    Link-local addresses, including cloud metadata, are always rejected.
    Private and loopback hosts are rejected in production unless the
    administrator set ISSUEBOT_ALLOW_PRIVATE_DOCSGPT.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise UnsafeURL("scheme")
    if parsed.scheme == "http" and production and not allow_private:
        raise UnsafeURL("https_required")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURL("host")
    if host in _BLOCKED_HOSTS and not (allow_private or not production):
        raise UnsafeURL("local_name")
    try:
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    allow_non_public = allow_private or not production
    if ip is not None:
        if _ip_blocked(ip, allow_private=allow_non_public):
            raise UnsafeURL("blocked_ip")
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = resolver(host, port)
    except OSError as exc:
        raise UnsafeURL("unresolvable") from exc
    if not infos:
        raise UnsafeURL("unresolvable")
    for info in infos:
        resolved = ipaddress.ip_address(info[4][0])
        if _ip_blocked(resolved, allow_private=allow_non_public):
            raise UnsafeURL("blocked_ip")


def source_is_linkable(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return not _ip_blocked(ip, allow_private=False)
