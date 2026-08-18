"""Tests for verified patent to generic research document adaptation."""

from __future__ import annotations

from datetime import date

import pytest

from app.research.patent_research_document_adapter import (
    PatentResearchDocumentAdapter,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.schemas.epo_ops_abstract import EpoOpsVerifiedPatentRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPurpose,
)
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentStatus,
)


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How can pressure sensors detect seat occupancy?",
        objective="Identify pressure sensors for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=2,
        maximum_bytes=4096,
    )


def verified_record(
    *,
    publication_number: str,
    title: str,
    abstract_text: str,
    publication_date: date,
    language: str | None = "en",
) -> EpoOpsVerifiedPatentRecord:
    return EpoOpsVerifiedPatentRecord(
        metadata=PatentSourceMetadata(
            source_family=PatentSourceFamily.EPO_OPS,
            publication_number=publication_number,
            title=title,
            source_url=(
                "https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/docdb/{publication_number}/abstract"
            ),
            metadata_verification_state=(PatentMetadataVerificationState.VERIFIED),
            publication_date=publication_date,
        ),
        abstract_text=abstract_text,
        abstract_language=language,
    )


def execution(
    records: tuple[EpoOpsVerifiedPatentRecord, ...],
) -> PatentResearchPlanExecutionResult:
    source_request = request()
    query = PatentSearchQuery(
        cql_query=(
            'ta all "pressure sensors" and ta all "seat occupancy" and pd < 20260818'
        ),
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    bibliographic_records = tuple(
        EpoOpsBibliographicRecord(
            publication_number=record.metadata.publication_number,
            publication_docdb=(
                f"{record.metadata.publication_number[:2]}."
                f"{record.metadata.publication_number[2:-2]}."
                f"{record.metadata.publication_number[-2:]}"
            ),
            title=record.metadata.title,
            publication_date=record.metadata.publication_date,
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/"
                "published-data/search/biblio?q=test"
            ),
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=None,
            title_language="en",
        )
        for record in records
    )
    search_request = EpoOpsSearchRequest(
        cql_query=query.cql_query,
        maximum_results=source_request.maximum_search_results,
    )
    collection = PatentResearchCollectionResult(
        request=source_request,
        search_result=EpoOpsBibliographicSearchResult(
            request=search_request,
            records=bibliographic_records,
        ),
        verified_records=records,
    )
    return PatentResearchPlanExecutionResult(
        query=query,
        collection=collection,
        attempted_queries=(query,),
    )


def test_adapter_maps_verified_patent_abstract_to_readable_document() -> None:
    abstract = (
        "A seat occupancy system uses pressure sensors to detect whether "
        "a person is seated and updates an occupancy state automatically."
    )
    result = PatentResearchDocumentAdapter().adapt(
        execution(
            (
                verified_record(
                    publication_number="EP123456A1",
                    title="Seat occupancy sensing system",
                    abstract_text=abstract,
                    publication_date=date(2025, 1, 15),
                ),
            )
        ),
        request_id="patent-analysis-001",
        task_id="technical-relevance",
    )

    assert result.request_id == "patent-analysis-001"
    assert len(result.documents) == 1

    document = result.documents[0]
    candidate = document.candidate

    assert document.status is ResearchSourceDocumentStatus.READ
    assert document.content_type is ResearchSourceContentType.TEXT
    assert document.content == abstract
    assert document.language == "en"
    assert document.word_count == len(abstract.split())
    assert document.character_count == len(abstract)
    assert document.reader == "verified-epo-patent-adapter"

    assert candidate.request_id == "patent-analysis-001"
    assert candidate.task_id == "technical-relevance"
    assert candidate.query_id == "patent-query-primary"
    assert candidate.title == "Seat occupancy sensing system"
    assert candidate.rank == 1
    assert candidate.published_at == date(2025, 1, 15)
    assert candidate.metadata["patent_publication_number"] == "EP123456A1"
    assert candidate.metadata["patent_source_family"] == "epo_ops"
    assert candidate.metadata["patent_verification_state"] == "verified"
    assert candidate.metadata["patent_query_purpose"] == "primary"
    assert candidate.metadata["search_query_text"].startswith(
        'ta all "pressure sensors"'
    )
    assert document.metadata["patent_publication_number"] == "EP123456A1"
    assert document.metadata["patent_abstract_language"] == "en"


def test_adapter_preserves_verified_record_order() -> None:
    records = (
        verified_record(
            publication_number="EP123456A1",
            title="First patent",
            abstract_text="First verified patent abstract text for analysis.",
            publication_date=date(2025, 1, 15),
        ),
        verified_record(
            publication_number="EP654321B1",
            title="Second patent",
            abstract_text="Second verified patent abstract text for analysis.",
            publication_date=date(2024, 6, 1),
        ),
    )

    result = PatentResearchDocumentAdapter().adapt(
        execution(records),
        request_id="patent-analysis-002",
        task_id="technical-relevance",
    )

    assert [
        document.candidate.metadata["patent_publication_number"]
        for document in result.documents
    ] == ["EP123456A1", "EP654321B1"]
    assert [document.candidate.rank for document in result.documents] == [1, 2]


def test_adapter_returns_empty_document_set_for_zero_verified_records() -> None:
    result = PatentResearchDocumentAdapter().adapt(
        execution(()),
        request_id="patent-analysis-003",
        task_id="technical-relevance",
    )

    assert result.request_id == "patent-analysis-003"
    assert result.documents == []


@pytest.mark.parametrize(
    ("request_id", "task_id", "message"),
    [
        (" ", "technical-relevance", "request_id must not be blank"),
        ("patent-analysis-004", " ", "task_id must not be blank"),
    ],
)
def test_adapter_rejects_blank_code_owned_identity(
    request_id: str,
    task_id: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        PatentResearchDocumentAdapter().adapt(
            execution(()),
            request_id=request_id,
            task_id=task_id,
        )


def test_adapter_omits_language_metadata_when_provider_has_no_language() -> None:
    result = PatentResearchDocumentAdapter().adapt(
        execution(
            (
                verified_record(
                    publication_number="EP123456A1",
                    title="Patent without language",
                    abstract_text="Verified abstract without a language code.",
                    publication_date=date(2025, 1, 15),
                    language=None,
                ),
            )
        ),
        request_id="patent-analysis-005",
        task_id="technical-relevance",
    )

    document = result.documents[0]

    assert document.language is None
    assert "patent_abstract_language" not in document.metadata
