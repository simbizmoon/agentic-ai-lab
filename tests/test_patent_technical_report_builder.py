"""Tests for deterministic patent technical report construction."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.research.patent_technical_report_builder import (
    DeterministicPatentTechnicalReportBuilder,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

CONTENT = "A seat pressure sensor detects occupancy."


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How is pressure-sensor-based seat occupancy detected?",
        objective="Find technically relevant patent publications.",
        prior_art_cutoff_date=date(2026, 8, 18),
        maximum_search_results=2,
        maximum_sources=1,
    )


def document_set() -> ResearchSourceDocumentSet:
    candidate = ResearchSourceCandidate(
        source_id="patent-source-001",
        request_id="request-001",
        task_id="patent-technical-relevance",
        query_id="patent-query-primary",
        title="Vehicle seat occupancy detection method",
        url="https://ops.epo.org/3.2/rest-services/example",
        source_type=ResearchSourceType.OTHER,
        snippet=CONTENT,
        published_at=date(2026, 1, 1),
        rank=1,
        metadata={
            "search_query_text": 'ta all "seat occupancy"',
            "patent_source_family": "epo_ops",
            "patent_publication_number": "CN122100948A",
            "patent_verification_state": "verified",
            "patent_query_purpose": "primary",
        },
    )
    document = ResearchSourceDocument(
        document_id="patent-document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="verified-epo-patent-adapter",
        metadata={
            "patent_source_family": "epo_ops",
            "patent_publication_number": "CN122100948A",
            "patent_verification_state": "verified",
            "patent_query_purpose": "primary",
            "patent_abstract_language": "en",
        },
    )
    return ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[document],
    )


def evidence(
    *,
    semantic_level: str = "directly_relevant",
    semantic_evaluated: str = "true",
) -> ResearchEvidence:
    return ResearchEvidence(
        evidence_id="patent-document-001-evidence-001",
        request_id="request-001",
        task_id="patent-technical-relevance",
        source_id="patent-source-001",
        document_id="patent-document-001",
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
        evidence_type=ResearchEvidenceType.FACT,
        stance=ResearchEvidenceStance.SUPPORTS,
        relevance_score=0.86,
        confidence_score=0.8,
        rationale=("The passage directly describes seat occupancy sensing."),
        metadata={
            "extractor": "semantic-paragraph-live-document",
            "selection_rank": "1",
            "embedding_rank": "1",
            "embedding_score": "0.9",
            "lexical_score": "0.8",
            "semantic_evaluated": semantic_evaluated,
            "semantic_relevance_level": semantic_level,
            **(
                {"semantic_relevance_score": "0.86"}
                if semantic_level != "unevaluated"
                else {}
            ),
        },
    )


def relevance_result(
    *,
    evidence_value: ResearchEvidence,
) -> tuple[
    PatentResearchRequest,
    PatentTechnicalRelevanceEvidenceResult,
]:
    value = request()
    documents = document_set()
    evidence_set = ResearchEvidenceSet(
        request_id="request-001",
        document_set=documents,
        evidence=[evidence_value],
    )
    metadata = PatentSourceMetadata(
        source_family=PatentSourceFamily.EPO_OPS,
        publication_number="CN122100948A",
        title="Vehicle seat occupancy detection method",
        source_url="https://ops.epo.org/3.2/rest-services/example",
        metadata_verification_state=(PatentMetadataVerificationState.VERIFIED),
        publication_date=date(2026, 1, 1),
    )
    record = SimpleNamespace(
        metadata=metadata,
        abstract_language="en",
    )
    execution = SimpleNamespace(
        collection=SimpleNamespace(
            request=value,
            verified_records=[record],
        ),
        query=SimpleNamespace(
            purpose=SimpleNamespace(value="primary"),
            cql_query='ta all "seat occupancy"',
        ),
    )
    relevance = PatentTechnicalRelevanceEvidenceResult(
        execution=execution,  # type: ignore[arg-type]
        document_set=documents,
        evidence_set=evidence_set,
    )
    return value, relevance


def test_builder_maps_relevant_evidence_with_exact_provenance() -> None:
    value, relevance = relevance_result(
        evidence_value=evidence(),
    )

    report = DeterministicPatentTechnicalReportBuilder().build(
        request=value,
        relevance=relevance,
        request_id="request-001",
    )

    assert report.finding_count == 1
    assert report.unevaluated_evidence_ids == []
    finding_value = report.findings[0]
    assert finding_value.publication_number == "CN122100948A"
    assert finding_value.relevance_level.value == "directly_relevant"
    assert finding_value.evidence.excerpt == CONTENT
    assert finding_value.evidence.start_character == 0
    assert finding_value.evidence.end_character == len(CONTENT)
    assert "does not determine novelty" in report.scope_notice


def test_builder_excludes_unevaluated_evidence_from_findings() -> None:
    value, relevance = relevance_result(
        evidence_value=evidence(
            semantic_level="unevaluated",
            semantic_evaluated="false",
        ),
    )

    report = DeterministicPatentTechnicalReportBuilder().build(
        request=value,
        relevance=relevance,
        request_id="request-001",
    )

    assert report.findings == []
    assert report.unevaluated_evidence_ids == ["patent-document-001-evidence-001"]
    assert report.input_evidence_count == 1


def test_builder_rejects_irrelevant_evidence_leakage() -> None:
    value, relevance = relevance_result(
        evidence_value=evidence(
            semantic_level="irrelevant",
            semantic_evaluated="true",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="irrelevant evidence",
    ):
        DeterministicPatentTechnicalReportBuilder().build(
            request=value,
            relevance=relevance,
            request_id="request-001",
        )


def test_builder_rejects_request_binding_drift() -> None:
    value, relevance = relevance_result(
        evidence_value=evidence(),
    )
    different = value.model_copy(update={"question": "Different question"})

    with pytest.raises(
        RuntimeError,
        match="exact request",
    ):
        DeterministicPatentTechnicalReportBuilder().build(
            request=different,
            relevance=relevance,
            request_id="request-001",
        )
