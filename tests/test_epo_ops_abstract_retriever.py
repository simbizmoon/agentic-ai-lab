"""Tests for EPO OPS abstract retrieval and verified source mapping."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.research.epo_ops_abstract_retriever import (
    EPO_OPS_ABSTRACT_ACCEPT,
    EpoOpsAbstractResponseError,
    EpoOpsAbstractRetriever,
    EpoOpsAbstractXmlParseError,
)
from app.research.epo_ops_client import EpoOpsHttpResponse
from app.research.epo_ops_patent_source_adapter import (
    EpoOpsPatentSourceMappingError,
    build_verified_epo_patent_record,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsDocumentIdType,
)
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
)

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "epo_ops"


def fixture(name: str) -> bytes:
    return (FIXTURE_DIRECTORY / name).read_bytes()


def bibliographic(**overrides: object) -> EpoOpsBibliographicRecord:
    values: dict[str, object] = {
        "publication_number": "EPTEST0001A1",
        "publication_docdb": "EP.TEST0001.A1",
        "title": "Test optical apparatus",
        "publication_date": date(2024, 1, 31),
        "source_endpoint": (
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
            "?q=ti%3D%22optical%20sensor%22"
        ),
        "document_id_type": EpoOpsDocumentIdType.DOCDB,
        "application_number": "EPTESTAPP0001",
        "title_language": "en",
    }
    values.update(overrides)
    return EpoOpsBibliographicRecord.model_validate(values)


class FakeEpoOpsClient:
    def __init__(
        self,
        *,
        body: bytes,
        content_type: str = EPO_OPS_ABSTRACT_ACCEPT,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.calls: list[tuple[str, str]] = []

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
    ) -> EpoOpsHttpResponse:
        self.calls.append((endpoint, accept))
        return EpoOpsHttpResponse(body=self.body, content_type=self.content_type)


def retriever(
    name: str = "abstract_valid.xml",
    *,
    content_type: str = EPO_OPS_ABSTRACT_ACCEPT,
) -> tuple[EpoOpsAbstractRetriever, FakeEpoOpsClient]:
    client = FakeEpoOpsClient(body=fixture(name), content_type=content_type)
    return EpoOpsAbstractRetriever(client=client), client  # type: ignore[arg-type]


def test_retrieval_uses_exact_docdb_abstract_endpoint() -> None:
    value, client = retriever()

    result = value.retrieve(bibliographic())

    assert result.publication_number == "EPTEST0001A1"
    assert result.publication_docdb == "EP.TEST0001.A1"
    assert result.abstract_text == (
        "Test optical apparatus with a bounded sensing mechanism."
    )
    assert result.abstract_language == "en"
    assert client.calls == [
        (
            (
                "https://ops.epo.org/3.2/rest-services/published-data/"
                "publication/docdb/EP.TEST0001.A1/abstract"
            ),
            "application/exchange+xml",
        )
    ]


def test_abstract_prefers_english_then_falls_back_to_first_nonblank() -> None:
    value, _ = retriever("abstract_fallback.xml")

    result = value.retrieve(bibliographic())

    assert result.abstract_text == "Erste technische Zusammenfassung."
    assert result.abstract_language == "de"


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "application/json", "application/ops+xml", ""],
)
def test_abstract_rejects_wrong_mime(content_type: str) -> None:
    value, _ = retriever(content_type=content_type)

    with pytest.raises(EpoOpsAbstractResponseError):
        value.retrieve(bibliographic())


def test_abstract_accepts_utf8_charset_parameter() -> None:
    value, _ = retriever(content_type="Application/Exchange+XML; charset=UTF-8")

    assert value.retrieve(bibliographic()).abstract_language == "en"


def test_abstract_rejects_missing_abstract() -> None:
    value, _ = retriever("abstract_missing.xml")

    with pytest.raises(EpoOpsAbstractResponseError, match="nonblank abstract"):
        value.retrieve(bibliographic())


def test_abstract_rejects_identity_mismatch() -> None:
    value, _ = retriever("abstract_mismatch.xml")

    with pytest.raises(EpoOpsAbstractResponseError, match="exactly one matching"):
        value.retrieve(bibliographic())


def test_abstract_rejects_unsafe_xml_without_payload_leak() -> None:
    value, _ = retriever("abstract_unsafe_entity.xml")

    with pytest.raises(EpoOpsAbstractXmlParseError) as captured:
        value.retrieve(bibliographic())

    rendered = str(captured.value) + repr(captured.value)
    assert "file:///etc/passwd" not in rendered


def test_verified_mapping_requires_exact_identity_and_exposes_abstract() -> None:
    value, _ = retriever()
    abstract = value.retrieve(bibliographic())

    verified = build_verified_epo_patent_record(
        bibliographic=bibliographic(),
        abstract=abstract,
    )

    assert verified.metadata.source_family is PatentSourceFamily.EPO_OPS
    assert verified.metadata.metadata_verification_state is (
        PatentMetadataVerificationState.VERIFIED
    )
    assert verified.metadata.publication_number == "EPTEST0001A1"
    assert verified.metadata.publication_date == date(2024, 1, 31)
    assert verified.metadata.source_url.endswith(
        "/publication/docdb/EP.TEST0001.A1/abstract"
    )
    assert verified.abstract_text == abstract.abstract_text


def test_verified_mapping_rejects_mismatched_publication() -> None:
    value, _ = retriever()
    abstract = value.retrieve(bibliographic())

    with pytest.raises(EpoOpsPatentSourceMappingError):
        build_verified_epo_patent_record(
            bibliographic=bibliographic(publication_number="EPOTHER0001A1"),
            abstract=abstract,
        )
