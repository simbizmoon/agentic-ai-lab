"""Offline tests for the no-redirect exact official-document reader."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.research.stage9_http_exact_official_document_reader import (
    Stage9HttpExactOfficialDocumentReader,
    Stage9OfficialDocumentContentTypeError,
    Stage9OfficialDocumentDomainError,
    Stage9OfficialDocumentPdfError,
    Stage9OfficialDocumentRedirectError,
)

CONTENT = (
    b"<html><title>NIST</title><script>hidden executable text</script>"
    b"<body><main><p>Exact GAI content.</p></main></body></html>"
)


def _pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


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
    assert document.content == "NIST\n\nExact GAI content."
    assert "hidden executable text" not in document.content
    assert b"<html" not in document.content.encode()
    assert (
        document.response_sha256
        == hashlib.sha256(document.content.encode("utf-8")).hexdigest()
    )
    assert document.url == "https://www.nist.gov/example"


def test_rejects_input_outside_allowlist_before_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    with pytest.raises(Stage9OfficialDocumentDomainError, match="allowlist"):
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

    with pytest.raises(Stage9OfficialDocumentRedirectError, match="redirect"):
        _reader(handler).read(url="https://www.nist.gov/example")

    assert calls == 1


def test_rejects_nontext_content_without_using_it_as_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"PNG-fixture",
            headers={"content-type": "image/png"},
            request=request,
        )

    with pytest.raises(Stage9OfficialDocumentContentTypeError, match="content type"):
        _reader(handler).read(url="https://www.nist.gov/example.png")


def test_extracts_bounded_text_from_an_official_pdf() -> None:
    pdf = _pdf_bytes("Exact NIST PDF evidence.")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=pdf,
            headers={"content-type": "application/pdf"},
            request=request,
        )

    document = _reader(handler).read(url="https://nvlpubs.nist.gov/example.pdf")

    assert document.content == "Exact NIST PDF evidence."
    assert (
        document.response_sha256
        == hashlib.sha256(document.content.encode("utf-8")).hexdigest()
    )


def test_rejects_a_pdf_without_extractable_text() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=output.getvalue(),
            headers={"content-type": "application/pdf"},
            request=request,
        )

    with pytest.raises(Stage9OfficialDocumentPdfError, match="extractable"):
        _reader(handler).read(url="https://nvlpubs.nist.gov/blank.pdf")
