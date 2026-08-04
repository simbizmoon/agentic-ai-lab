"""Tests for deterministic research quality evaluation."""

from datetime import date

import pytest

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
from app.schemas.research_quality import (
    ResearchQualityIssueCode,
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
    """Return one complete quality-evaluation workspace."""

    request = ResearchRequest(
        request_id="research-001",
        question="How does agent memory work?",
        objective=(
            "Explain agent memory using traceable evidence."
        ),
    )

    graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="research-001",
                title="Agent memory findings",
                question="How does agent memory work?",
                objective=(
                    "Produce verified agent-memory findings."
                ),
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
        author="Example Author",
        publisher="Example Publisher",
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

    quality = ResearchSourceQualityEvaluation(
        document=document,
        evaluator="test-source-quality",
        authority_score=0.9,
        primary_source_score=0.8,
        recency_score=1.0,
        completeness_score=0.45,
        traceability_score=1.0,
        overall_score=0.77,
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
        source_quality_evaluations=[quality],
    )


def test_evaluator_scores_complete_report() -> None:
    value = workspace()
    report = (
        DeterministicResearchSynthesizer()
        .synthesize(value)
    )

    result = ResearchQualityEvaluator().evaluate(
        workspace=value,
        report=report,
    )

    assert result.claim_coverage_score == 1.0
    assert result.citation_coverage_score == 1.0
    assert result.source_diversity_score == 1.0
    assert result.source_quality_score == 0.77
    assert result.contradiction_handling_score == 1.0
    assert result.passed is True


def test_evaluator_uses_neutral_quality_without_evaluations() -> None:
    value = workspace().model_copy(
        update={
            "source_quality_evaluations": [],
        }
    )
    report = (
        DeterministicResearchSynthesizer()
        .synthesize(value)
    )

    result = ResearchQualityEvaluator().evaluate(
        workspace=value,
        report=report,
    )

    assert result.source_quality_score == 0.5
    assert any(
        issue.code
        is ResearchQualityIssueCode.LOW_SOURCE_QUALITY
        for issue in result.issues
    )


def test_evaluator_rejects_workspace_mismatch() -> None:
    value = workspace()
    report = (
        DeterministicResearchSynthesizer()
        .synthesize(value)
        .model_copy(
            update={
                "workspace_id": "different-workspace",
            }
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "report workspace_id must match workspace"
        ),
    ):
        ResearchQualityEvaluator().evaluate(
            workspace=value,
            report=report,
        )


def test_evaluator_rejects_blank_name() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        ResearchQualityEvaluator(name=" ")


def test_evaluation_is_deterministic() -> None:
    value = workspace()
    report = (
        DeterministicResearchSynthesizer()
        .synthesize(value)
    )
    evaluator = ResearchQualityEvaluator()

    first = evaluator.evaluate(
        workspace=value,
        report=report,
    )
    second = evaluator.evaluate(
        workspace=value,
        report=report,
    )

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
