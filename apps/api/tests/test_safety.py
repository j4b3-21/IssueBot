"""Signature, redaction, URL policy, and report trust rules."""

import hashlib
import hmac

import pytest
from issuebot.docsgpt import DocsGPTResult
from issuebot.report import build_report, render_comment
from issuebot.safety import (
    UnsafeURL,
    assess_url,
    github_signature_matches,
    neutralize_mentions,
    redact,
    source_is_linkable,
)

BODY = b'{"zen":"Keep it logically awesome."}'
DIGEST = "84a59e1d9d95f2c974c894bde78271de162e4f62be53c1031148a01036aa324a"


def test_known_hmac_vector():
    expected = hmac.new(b"test-webhook-secret", BODY, hashlib.sha256).hexdigest()
    assert expected == DIGEST
    assert github_signature_matches("test-webhook-secret", BODY, "sha256=" + DIGEST)
    assert not github_signature_matches("test-webhook-secret", BODY + b" ", "sha256=" + DIGEST)
    assert not github_signature_matches("", BODY, "sha256=" + DIGEST)
    assert not github_signature_matches("test-webhook-secret", BODY, "sha1=" + DIGEST)


def test_redact_secrets():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----"
    text = redact(f"Authorization: Bearer ghs_testtokenvalue api_key=super-secret {pem}")
    assert "ghs_testtokenvalue" not in text
    assert "super-secret" not in text
    assert "BEGIN RSA PRIVATE KEY" not in text


def test_mentions_are_broken():
    text = neutralize_mentions("Ping @octocat and @acme/maintainers")
    assert "@octocat" not in text
    assert "@acme/maintainers" not in text


def test_outbound_policy():
    def resolver(host, port):
        assert host == "docs.example"
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    assess_url(
        "https://docs.example/api/answer", production=True, allow_private=False, resolver=resolver
    )
    with pytest.raises(UnsafeURL):
        assess_url(
            "http://169.254.169.254/", production=False, allow_private=True, resolver=resolver
        )
    with pytest.raises(UnsafeURL):
        assess_url(
            "http://127.0.0.1:7091/api/answer",
            production=True,
            allow_private=False,
            resolver=resolver,
        )
    assess_url(
        "http://127.0.0.1:7091/api/answer", production=True, allow_private=True, resolver=resolver
    )
    assess_url(
        "http://127.0.0.1:7091/api/answer", production=False, allow_private=False, resolver=resolver
    )
    with pytest.raises(UnsafeURL):
        assess_url("file:///etc/passwd", production=False, allow_private=True, resolver=resolver)
    with pytest.raises(UnsafeURL):
        assess_url(
            "http://example.com/api/answer", production=True, allow_private=False, resolver=resolver
        )

    def loopback(_host, port):
        return [(2, 1, 6, "", ("127.0.0.1", port))]

    with pytest.raises(UnsafeURL):
        assess_url(
            "https://evil.example/api/answer",
            production=True,
            allow_private=False,
            resolver=loopback,
        )


def test_source_links_reject_javascript_and_metadata():
    assert source_is_linkable("https://docs.example.com/install")
    assert not source_is_linkable("javascript:alert(1)")
    assert not source_is_linkable("http://169.254.169.254/")
    assert not source_is_linkable("https://localhost/admin")


def test_facts_without_sources_are_demoted():
    result = DocsGPTResult(
        answer='{"summary":"x","documented_facts":[{"text":"The disk is full."}],"hypotheses":["Maybe."]}',
        sources=[],
        conversation_id=None,
        structured=None,
        correlation_id="c",
    )
    report = build_report(result, [], None, mock=False)
    assert report["documented_facts"] == []
    assert any("disk is full" in item for item in report["unknowns"])
    assert "http://evil.example" not in str(report["sources"])


def test_fabricated_url_in_answer_is_not_a_source():
    result = DocsGPTResult(
        answer='{"summary":"See http://evil.example/not-real","documented_facts":[{"text":"Guide says set the key."}]}',
        sources=[
            {
                "title": "Install",
                "source": "https://docs.example.com/install",
                "text": "Set the key.",
            }
        ],
        conversation_id="c",
        structured=None,
        correlation_id="c",
    )
    report = build_report(result, [], None, mock=False)
    urls = [item["url"] for item in report["sources"]]
    assert urls == ["https://docs.example.com/install"]
    assert report["documented_facts"]


def test_comment_lists_only_docsgpt_sources():
    result = DocsGPTResult(
        answer='{"summary":"See http://evil.example/x","documented_facts":[{"text":"Set the key."}]}',
        sources=[
            {"title": "Guide [1]", "source": "https://docs.example.com/@team/guide (v2)"},
            {"title": "notes.md", "source": "notes.md"},
            {"title": "Internal", "source": "http://169.254.169.254/latest"},
        ],
        conversation_id="c",
        structured=None,
        correlation_id="c",
    )
    body = render_comment("id", "acme/widget", 7, build_report(result, [], None, mock=False))
    sources = body.split("### Sources", 1)[1]
    assert "[Guide \\[1\\]](https://docs.example.com/%40team/guide%20%28v2%29)" in sources
    assert "- notes.md" in sources
    assert "169.254" not in sources
    assert "evil.example" not in sources
    assert "\u200b" not in sources.split("A maintainer")[0]
