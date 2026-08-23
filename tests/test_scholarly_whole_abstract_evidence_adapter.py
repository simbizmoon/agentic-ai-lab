"""Tests for exact whole-abstract evidence adaptation."""

from __future__ import annotations

import pytest

from app.research.bounded_scholarly_search_workflow import (
    BoundedScholarlySearchWorkflow,
)
from app.research.scholarly_abstract_document_adapter import (
    ScholarlyAbstractDocumentAdapter,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.research.scholarly_whole_abstract_evidence_adapter import (
    ScholarlyWholeAbstractEvidenceAdapter,
)
from app.schemas.research_evidence import (
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.scholarly_provider import (
    ScholarlyProviderUsage,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self, result: ScholarlySearchResult) -> None:
        self._result = result

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        return self._result


def _document_adaptation(*, include_abstract: bool = True):
    request = ScholarlySearchRequest(
        request_id="request-001",
        query="bounded academic evidence",
        maximum_results=1,
        maximum_provider_requests=1,
    )
    abstract_text = "Exact provider abstract used as a single evidence unit."
    work = ScholarlyWork(
        work_id="work-001",
        title="A scholarly evidence fixture",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=(
            normalize_scholarly_identifier(
                ScholarlyIdentifierType.OPENALEX,
                "W123",
            ),
        ),
        abstract=(
            ScholarlyAbstract(
                text=abstract_text,
                language="en",
                provider="fixture-provider",
                provider_record_id="record-001",
                source_url="https://api.example.test/record-001",
            )
            if include_abstract
            else None
        ),
        access=ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url="https://example.test/work-001",
        ),
        provenance=ScholarlyProviderProvenance(
            provider="fixture-provider",
            provider_record_id="record-001",
            request_url="https://api.example.test/record-001",
            retrieved_at="2026-08-23T12:00:00+09:00",
            response_sha256="a" * 64,
        ),
    )
    result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.SUCCEEDED,
        works=(work,),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=1,
            records_accepted=1,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    artifact = BoundedScholarlySearchWorkflow(provider=FixtureProvider(result)).run(
        request
    )
    return ScholarlyAbstractDocumentAdapter().adapt(
        artifact,
        task_id="task-001",
    )


def test_creates_one_exact_whole_abstract_evidence() -> None:
    documents = _document_adaptation()

    adaptation = ScholarlyWholeAbstractEvidenceAdapter().adapt(documents)

    assert len(adaptation.evidence_set.evidence) == 1
    document = documents.document_set.documents[0]
    evidence = adaptation.evidence_set.evidence[0]
    assert evidence.excerpt == document.content
    assert evidence.start_character == 0
    assert evidence.end_character == len(document.content)
    assert evidence.section_id == document.sections[0].section_id
    assert evidence.source_id == document.candidate.source_id
    assert evidence.document_id == document.document_id


def test_marks_semantic_assessments_as_not_performed() -> None:
    adaptation = ScholarlyWholeAbstractEvidenceAdapter().adapt(_document_adaptation())

    evidence = adaptation.evidence_set.evidence[0]
    assert evidence.evidence_type is ResearchEvidenceType.OTHER
    assert evidence.stance is ResearchEvidenceStance.NEUTRAL
    assert evidence.relevance_score == 0.0
    assert evidence.confidence_score == 0.0
    assert evidence.metadata["relevance_assessment"] == "not_performed"
    assert evidence.metadata["confidence_assessment"] == "not_performed"
    assert evidence.metadata["paper_quality_assessment"] == "not_performed"
    assert evidence.metadata["citation_impact_assessment"] == "not_performed"


def test_preserves_scholarly_identity_and_response_provenance() -> None:
    adaptation = ScholarlyWholeAbstractEvidenceAdapter().adapt(_document_adaptation())

    evidence = adaptation.evidence_set.evidence[0]
    assert evidence.metadata["scholarly_work_id"] == "work-001"
    assert evidence.metadata["scholarly_provider"] == "fixture-provider"
    assert evidence.metadata["scholarly_provider_record_id"] == "record-001"
    assert evidence.metadata["scholarly_response_sha256"] == "a" * 64
    assert evidence.metadata["scholarly_doi"] == "ABSENT"
    assert evidence.metadata["evidence_scope"] == ("provider_supplied_abstract_only")


def test_work_without_abstract_produces_no_document_and_no_evidence() -> None:
    documents = _document_adaptation(include_abstract=False)

    adaptation = ScholarlyWholeAbstractEvidenceAdapter().adapt(documents)

    assert documents.omitted_work_ids == ("work-001",)
    assert documents.document_set.documents == []
    assert adaptation.evidence_set.evidence == []


def test_evidence_id_is_stable_across_repeated_adaptation() -> None:
    documents = _document_adaptation()
    adapter = ScholarlyWholeAbstractEvidenceAdapter()

    first = adapter.adapt(documents)
    second = adapter.adapt(documents)

    assert first == second
    assert first.evidence_set.evidence[0].evidence_id.endswith(
        "-whole-abstract-evidence"
    )


def test_rejects_non_whole_abstract_section() -> None:
    documents = _document_adaptation()
    document = documents.document_set.documents[0]
    shortened_section = document.sections[0].model_copy(
        update={
            "content": document.content[:-1],
            "end_character": len(document.content) - 1,
        }
    )
    invalid_document = document.model_copy(update={"sections": [shortened_section]})
    invalid_set = documents.document_set.model_copy(
        update={"documents": [invalid_document]}
    )
    invalid_adaptation = documents.model_copy(update={"document_set": invalid_set})

    with pytest.raises(ValueError, match="whole document"):
        ScholarlyWholeAbstractEvidenceAdapter().adapt(invalid_adaptation)
