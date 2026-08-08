"""Tests for pipeline evidence and claim components."""

from __future__ import annotations

from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

CONTENT = "Grounded research connects claims to evidence."


def candidate(
    *,
    source_id: str,
    query_id: str,
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="request-001",
        task_id="task-001",
        query_id=query_id,
        title="Grounded research",
        url=(
            "https://local.aira.invalid/source/"
            f"{source_id}"
        ),
        source_type=ResearchSourceType.OTHER,
        rank=1,
    )


def document(
    *,
    source_id: str = "source-001",
    query_id: str = "query-001",
) -> ResearchSourceDocument:
    """Return one readable research document."""

    return ResearchSourceDocument(
        document_id=f"document-{source_id}",
        candidate=candidate(
            source_id=source_id,
            query_id=query_id,
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )


class StubEvidenceExtractor(ResearchEvidenceExtractor):
    """Extract the complete document as supporting evidence."""

    @property
    def name(self) -> str:
        """Return the extractor name."""

        return "stub-evidence-extractor"

    def extract(
        self,
        source_document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        """Return one evidence item for a document."""

        source = source_document.candidate
        evidence = ResearchEvidence(
            evidence_id=(
                f"evidence-{source.source_id}"
            ),
            request_id=source.request_id,
            task_id=source.task_id,
            source_id=source.source_id,
            document_id=source_document.document_id,
            excerpt=source_document.content,
            start_character=0,
            end_character=len(source_document.content),
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=1.0,
            confidence_score=0.9,
        )

        return ResearchEvidenceExtractionResult(
            document=source_document,
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor=self.name,
            evidence=[evidence],
            duration_ms=0,
        )


def test_evidence_adapter_combines_document_results() -> None:
    document_set = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[
            document(),
            document(
                source_id="source-002",
                query_id="query-002",
            ),
        ],
    )

    evidence_set = PipelineEvidenceExtractorAdapter(
        StubEvidenceExtractor()
    ).extract(document_set)

    assert evidence_set.request_id == "request-001"
    assert len(evidence_set.evidence) == 2
    assert [
        item.source_id
        for item in evidence_set.evidence
    ] == [
        "source-001",
        "source-002",
    ]


def test_evidence_adapter_skips_failed_documents() -> None:
    readable = document()
    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=candidate(
            source_id="source-failed",
            query_id="query-failed",
        ),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        content="",
        language=None,
        sections=[],
        word_count=0,
        character_count=0,
        reader="test-reader",
        error={
            "error_type": "ReadFailure",
            "message": "Could not read document.",
            "retryable": False,
        },
    )
    document_set = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[readable, failed],
    )

    evidence_set = PipelineEvidenceExtractorAdapter(
        StubEvidenceExtractor()
    ).extract(document_set)

    assert len(evidence_set.evidence) == 1
    assert evidence_set.evidence[0].source_id == "source-001"



class UsageStubEvidenceExtractor(StubEvidenceExtractor):
    def extract(self, source_document):
        result = super().extract(source_document)
        return result.model_copy(
            update={
                'metadata': {
                    **result.metadata,
                    'semantic_budget_attempts': '2',
                    'semantic_budget_recorded_tokens': '100',
                    'semantic_budget_elapsed_seconds': '1.5',
                }
            }
        )


def test_evidence_adapter_accumulates_usage_until_reset() -> None:
    adapter = PipelineEvidenceExtractorAdapter(
        UsageStubEvidenceExtractor()
    )
    first = ResearchSourceDocumentSet(
        request_id='request-001',
        documents=[document()],
    )
    second = ResearchSourceDocumentSet(
        request_id='request-001',
        documents=[document(source_id='source-002', query_id='query-002')],
    )
    adapter.extract(first)
    adapter.extract(second)
    assert adapter.last_usage.attempts == 4
    assert adapter.last_usage.recorded_tokens == 200
    assert adapter.last_usage.elapsed_seconds == 3.0
    adapter.reset_usage()
    assert adapter.last_usage.attempts == 0
    assert adapter.last_usage.recorded_tokens == 0
    assert adapter.last_usage.elapsed_seconds == 0.0


def test_claim_builder_creates_traceable_supported_claim() -> None:
    document_set = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[document()],
    )
    evidence_set = PipelineEvidenceExtractorAdapter(
        StubEvidenceExtractor()
    ).extract(document_set)

    claim_set = DeterministicPipelineClaimBuilder().build(
        evidence_set
    )

    assert len(claim_set.claims) == 1

    claim = claim_set.claims[0]
    evidence = evidence_set.evidence[0]
    citation = claim.citations[0]

    assert claim.text == evidence.excerpt
    assert claim.status.value == "supported"
    assert claim.supporting_evidence_ids == [
        evidence.evidence_id
    ]
    assert citation.evidence_id == evidence.evidence_id
    assert citation.excerpt == evidence.excerpt
    assert (
        citation.start_character
        == evidence.start_character
    )
    assert citation.end_character == evidence.end_character


def test_claim_builder_returns_empty_set_for_no_evidence() -> None:
    document_set = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[document()],
    )
    evidence_set = PipelineEvidenceExtractorAdapter(
        StubEvidenceExtractor()
    ).extract(document_set).model_copy(
        update={"evidence": []}
    )

    claim_set = DeterministicPipelineClaimBuilder().build(
        evidence_set
    )

    assert claim_set.claims == []
