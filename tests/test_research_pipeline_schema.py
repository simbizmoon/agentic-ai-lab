"""Tests for the single research pipeline result schema."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.research.research_quality_evaluator import (
    ResearchQualityEvaluator,
)
from app.research.research_synthesizer import (
    DeterministicResearchSynthesizer,
)
from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
    ResearchClaimSet,
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
    ResearchSourceQualityLevel,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
)

CONTENT = "Agent memory stores contextual information."


def workspace() -> ResearchWorkspace:
    """Return one complete research workspace."""

    request = ResearchRequest(
        request_id="research-001",
        question="How does agent memory work?",
        objective="Explain agent memory.",
    )

    graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="research-001",
                title="Agent memory",
                question="How does agent memory work?",
                objective="Produce verified findings.",
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Structured findings.",
            )
        ],
    )

    queries = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-001",
                request_id="research-001",
                task_id="task-001",
                query_text="agent memory",
            )
        ],
    )

    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        published_at=date(2026, 1, 1),
        rank=1,
    )

    candidates = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=queries,
        candidates=[candidate],
    )

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )

    documents = ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[document],
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-001",
        request_id="research-001",
        task_id="task-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
        evidence_type=ResearchEvidenceType.FACT,
        stance=ResearchEvidenceStance.SUPPORTS,
        relevance_score=0.9,
        confidence_score=0.8,
    )

    evidence_set = ResearchEvidenceSet(
        request_id="research-001",
        document_set=documents,
        evidence=[evidence],
    )

    citation = ResearchCitation(
        citation_id="citation-001",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
    )

    claim = ResearchClaim(
        claim_id="claim-001",
        request_id="research-001",
        task_id="task-001",
        text=CONTENT,
        claim_type=ResearchClaimType.FACTUAL,
        status=ResearchClaimStatus.SUPPORTED,
        confidence_score=0.8,
        citations=[citation],
        supporting_evidence_ids=[
            "evidence-001"
        ],
    )

    claims = ResearchClaimSet(
        request_id="research-001",
        evidence_set=evidence_set,
        claims=[claim],
    )

    source_quality = ResearchSourceQualityEvaluation(
        document=document,
        evaluator="test-evaluator",
        authority_score=0.9,
        primary_source_score=0.8,
        recency_score=1.0,
        completeness_score=0.45,
        traceability_score=0.75,
        overall_score=0.75,
        quality_level=ResearchSourceQualityLevel.HIGH,
    )

    return ResearchWorkspace(
        workspace_id="workspace-001",
        request=request,
        task_graph=graph,
        query_set=queries,
        candidate_set=candidates,
        document_set=documents,
        evidence_set=evidence_set,
        claim_set=claims,
        source_quality_evaluations=[
            source_quality
        ],
    )


def result() -> SingleResearchPipelineResult:
    """Return one valid pipeline result."""

    value = workspace()
    report = (
        DeterministicResearchSynthesizer()
        .synthesize(value)
    )
    quality = ResearchQualityEvaluator().evaluate(
        workspace=value,
        report=report,
    )

    return SingleResearchPipelineResult(
        workspace=value,
        report=report,
        quality=quality,
    )


def test_pipeline_result_accepts_valid_values() -> None:
    value = result()

    assert value.report.workspace_id == (
        value.workspace.workspace_id
    )
    assert value.quality.report == value.report


def test_pipeline_result_rejects_workspace_mismatch() -> None:
    value = result()
    report = value.report.model_copy(
        update={
            "workspace_id": "different-workspace",
        }
    )

    with pytest.raises(
        ValidationError,
        match=(
            "report workspace_id must match workspace"
        ),
    ):
        SingleResearchPipelineResult(
            workspace=value.workspace,
            report=report,
            quality=value.quality,
        )


def test_pipeline_result_rejects_quality_report_mismatch() -> None:
    value = result()
    different_report = value.report.model_copy(
        update={
            "title": "Different title",
        }
    )

    with pytest.raises(
        ValidationError,
        match=(
            "quality report must match pipeline report"
        ),
    ):
        SingleResearchPipelineResult(
            workspace=value.workspace,
            report=different_report,
            quality=value.quality,
        )



def test_pipeline_result_defaults_to_empty_claim_relevance_evaluations() -> None:
    value = result()

    assert value.claim_relevance_evaluations == []
