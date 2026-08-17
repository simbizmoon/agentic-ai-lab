"""Tests for bounded EPO OPS CQL bibliographic search."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from app.research.epo_ops_bibliographic_searcher import (
    EPO_OPS_SEARCH_ACCEPT,
    EPO_OPS_SEARCH_URL,
    EpoOpsBibliographicResponseError,
    EpoOpsBibliographicSearcher,
    EpoOpsXmlParseError,
)
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "epo_ops"


def fixture(name: str) -> bytes:
    return (FIXTURE_DIRECTORY / name).read_bytes()


class FakeEpoOpsClient:
    def __init__(
        self,
        *,
        body: bytes,
        content_type: str = EPO_OPS_SEARCH_ACCEPT,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.calls: list[tuple[str, str, dict[str, str] | None]] = []

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
        extra_headers: dict[str, str] | None = None,
    ) -> EpoOpsHttpResponse:
        self.calls.append((endpoint, accept, extra_headers))
        return EpoOpsHttpResponse(body=self.body, content_type=self.content_type)


def searcher(
    name: str = "valid_one.xml",
    *,
    content_type: str = EPO_OPS_SEARCH_ACCEPT,
) -> tuple[EpoOpsBibliographicSearcher, FakeEpoOpsClient]:
    client = FakeEpoOpsClient(body=fixture(name), content_type=content_type)
    return EpoOpsBibliographicSearcher(client=client), client  # type: ignore[arg-type]


def request(**overrides: object) -> EpoOpsSearchRequest:
    values: dict[str, object] = {
        "cql_query": 'ti="optical sensor"',
        "maximum_results": 8,
    }
    values.update(overrides)
    return EpoOpsSearchRequest.model_validate(values)


def test_search_request_is_strict_frozen_and_bounded() -> None:
    value = request()

    assert value.maximum_results == 8
    with pytest.raises(ValidationError):
        request(cql_query=" ")
    with pytest.raises(ValidationError):
        request(maximum_results=0)
    with pytest.raises(ValidationError):
        request(maximum_results=9)
    with pytest.raises(ValidationError):
        request(maximum_results="8")
    with pytest.raises(ValidationError):
        value.maximum_results = 4


def test_search_uses_exact_encoded_endpoint_range_and_accept() -> None:
    value, client = searcher()

    result = value.search(request(maximum_results=4))

    assert len(result.records) == 1
    endpoint, accept, extra_headers = client.calls[0]
    parsed = urlsplit(endpoint)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == EPO_OPS_SEARCH_URL
    assert parsed.path.endswith("/published-data/search/biblio")
    assert parse_qs(parsed.query) == {"q": ['ti="optical sensor"']}
    assert "Range=" not in parsed.query
    assert "%20" in parsed.query
    assert "+" not in parsed.query
    assert accept == "application/exchange+xml"
    assert extra_headers == {"X-OPS-Range": "1-4"}


@pytest.mark.parametrize(
    "content_type",
    [
        "text/html",
        "application/json",
        "application/ops+xml",
        "",
    ],
)
def test_search_rejects_unaccepted_mime(content_type: str) -> None:
    value, _ = searcher(content_type=content_type)

    with pytest.raises(EpoOpsBibliographicResponseError):
        value.search(request())


def test_search_accepts_only_utf8_charset_parameter() -> None:
    value, _ = searcher(
        content_type="Application/Exchange+XML; charset=UTF-8",
    )
    assert len(value.search(request()).records) == 1

    rejected, _ = searcher(
        content_type="application/exchange+xml; boundary=value",
    )
    with pytest.raises(EpoOpsBibliographicResponseError):
        rejected.search(request())


def test_search_rejects_blank_body() -> None:
    client = FakeEpoOpsClient(body=b"   ")
    value = EpoOpsBibliographicSearcher(client=client)  # type: ignore[arg-type]

    with pytest.raises(EpoOpsBibliographicResponseError):
        value.search(request())


def test_parser_extracts_docdb_record_and_prefers_english_title() -> None:
    value, _ = searcher()

    record = value.search(request()).records[0]

    assert record.publication_number == "EPTEST0001A1"
    assert record.publication_docdb == "EP.TEST0001.A1"
    assert record.document_id_type is EpoOpsDocumentIdType.DOCDB
    assert record.title == "Test optical apparatus"
    assert record.title_language == "en"
    assert record.publication_date == date(2024, 1, 31)
    assert record.application_number == "EPTESTAPP0001"
    assert record.source_endpoint.startswith(EPO_OPS_SEARCH_URL)


def test_title_falls_back_to_first_nonblank_document_order() -> None:
    value, _ = searcher("multiple.xml")

    records = value.search(request()).records

    assert records[0].title == "Erster Testtitel"
    assert records[0].title_language == "de"


def test_exact_publication_dedup_preserves_different_kind_codes() -> None:
    value, _ = searcher("multiple.xml")

    records = value.search(request()).records

    assert [record.publication_number for record in records] == [
        "EPTEST0002A1",
        "EPTEST0002B1",
    ]


def test_missing_optional_publication_date_is_none() -> None:
    value, _ = searcher("missing_date.xml")

    assert value.search(request()).records[0].publication_date is None


@pytest.mark.parametrize(
    ("name", "error_type"),
    [
        ("malformed.xml", EpoOpsXmlParseError),
        ("unsafe_entity.xml", EpoOpsXmlParseError),
        ("unexpected_root.xml", EpoOpsBibliographicResponseError),
        ("missing_identity.xml", EpoOpsBibliographicResponseError),
        ("invalid_date.xml", EpoOpsBibliographicResponseError),
    ],
)
def test_invalid_or_unsafe_xml_is_rejected_without_payload_leak(
    name: str,
    error_type: type[Exception],
) -> None:
    value, _ = searcher(name)

    with pytest.raises(error_type) as captured:
        value.search(request())

    rendered = str(captured.value) + repr(captured.value)
    assert "file:///etc/passwd" not in rendered
    assert "Missing identity" not in rendered
    assert "20240230" not in rendered


def test_generic_publication_normalizer_remains_provider_neutral() -> None:
    assert normalize_patent_publication_number(" ep test-1.a1 ") == "EPTEST-1.A1"
