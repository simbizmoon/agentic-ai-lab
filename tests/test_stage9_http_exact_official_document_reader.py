"""Offline tests for the no-redirect exact official-document reader."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
import pytest

from app.research.stage9_http_exact_official_document_reader import (
    Stage9HttpExactOfficialDocumentReader,
    Stage9HttpExactOfficialDocumentReaderError,
)

CONTENT = b"<html><title>NIST</title><body>Exact GAI content.</body></html>"


def _reader(handler):
    return Stage9HttpExactOfficialDocumentReader(
        allowed_domains=("nist.gov",),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    )


def test_reads_one_exact_official_text_document_without_redirects() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=CONTENT,
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )

    document = _reader(handler).read(url="https://www.nist.gov/example")

    assert len(seen) == 1
    assert document.content == CONTENT.decode()
    assert document.response_sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert document.url == "https://www.nist.gov/example"


def test_rejects_input_outside_allowlist_before_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    with pytest.raises(Stage9HttpExactOfficialDocumentReaderError, match="allowlist"):
        _reader(handler).read(url="https://example.com/untrusted")


def test_does_not_follow_redirects() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"location": "https://example.com/redirect"},
            request=request,
        )

    with pytest.raises(Stage9HttpExactOfficialDocumentReaderError, match="redirect"):
        _reader(handler).read(url="https://www.nist.gov/example")

    assert calls == 1


def test_rejects_nontext_content_without_using_it_as_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"%PDF-fixture",
            headers={"content-type": "application/pdf"},
            request=request,
        )

    with pytest.raises(
        Stage9HttpExactOfficialDocumentReaderError, match="content type"
    ):
        _reader(handler).read(url="https://nvlpubs.nist.gov/example.pdf")
