"""End-to-end tests for the single research-agent pipeline."""

from datetime import date

import pytest

from app.research.research_pipeline_error import (
    ResearchPipelineError,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
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
    ResearchWorkspaceStage,
)

CONTENT = "Agent memory stores contextual information."


class FakeRequestValidator:
    """Accept a valid research request."""

    def validate(
        self,
        request: ResearchRequest,
    ) -> None:
        if not request.question.strip():
            raise ValueError(
                "question must not be blank"
            )


class FakeTaskDecomposer:
    """Produce one deterministic task."""

    def decompose(
        self,
        request: ResearchRequest,
    ) -> ResearchTaskGraph:
        return ResearchTaskGraph(
            request_id=request.request_id,
            tasks=[
                ResearchTask(
                    task_id="task-001",
                    request_id=request.request_id,
                    title="Agent memory findings",
                    question=request.question,
                    objective=request.objective,
                    completion_criteria=[
                        "Produce one supported finding"
                    ],
                    expected_output="Structured findings.",
                )
            ],
        )


class FakeQueryPlanner:
    """Produce one deterministic search query."""

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
    ) -> ResearchSearchQuerySet:
        return ResearchSearchQuerySet(
            request_id=request.request_id,
            task_graph=task_graph,
            queries=[
                ResearchSearchQuery(
                    query_id="query-001",
                    request_id=request.request_id,
                    task_id="task-001",
                    query_text="agent memory architecture",
                )
            ],
        )


class FakeSourceSearcher:
    """Produce one deterministic source candidate."""

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=[
                ResearchSourceCandidate(
                    source_id="source-001",
                    request_id=query_set.request_id,
                    task_id="task-001",
                    query_id="query-001",
                    title="Agent memory research",
                    url="https://example.com/source",
                    source_type=(
                        ResearchSourceType.ACADEMIC
                    ),
                    author="Example Author",
                    publisher="Example Publisher",
                    published_at=date(2026, 1, 1),
                    rank=1,
                )
            ],
        )


class EmptySourceSearcher:
    """Produce no source candidates."""

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=[],
        )


class FakeSourceReader:
    """Read one deterministic source document."""

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        candidate = candidate_set.candidates[0]

        return ResearchSourceDocumentSet(
            request_id=candidate_set.request_id,
            documents=[
                ResearchSourceDocument(
                    document_id="document-001",
                    candidate=candidate,
                    status=(
                        ResearchSourceDocumentStatus.READ
                    ),
                    content_type=(
                        ResearchSourceContentType.TEXT
                    ),
                    content=CONTENT,
                    language="en",
                    sections=[],
                    word_count=len(CONTENT.split()),
                    character_count=len(CONTENT),
                    reader="fake-reader",
                )
            ],
        )


class FakeEvidenceExtractor:
    """Extract one deterministic evidence item."""

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        document = document_set.documents[0]

        evidence = ResearchEvidence(
            evidence_id="evidence-001",
            request_id=document_set.request_id,
            task_id=document.candidate.task_id,
            source_id=document.candidate.source_id,
            document_id=document.document_id,
            excerpt=CONTENT,
            start_character=0,
            end_character=len(CONTENT),
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=0.9,
            confidence_score=0.8,
        )

        return ResearchEvidenceSet(
            request_id=document_set.request_id,
            document_set=document_set,
            evidence=[evidence],
        )


class FakeClaimBuilder:
    """Build one deterministic supported claim."""

    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet:
        evidence = evidence_set.evidence[0]

        citation = ResearchCitation(
            citation_id="citation-001",
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            document_id=evidence.document_id,
            excerpt=evidence.excerpt,
            start_character=evidence.start_character,
            end_character=evidence.end_character,
        )

        claim = ResearchClaim(
            claim_id="claim-001",
            request_id=evidence.request_id,
            task_id=evidence.task_id,
            text=evidence.excerpt,
            claim_type=ResearchClaimType.FACTUAL,
            status=ResearchClaimStatus.SUPPORTED,
            confidence_score=evidence.confidence_score,
            citations=[citation],
            supporting_evidence_ids=[
                evidence.evidence_id
            ],
        )

        return ResearchClaimSet(
            request_id=evidence_set.request_id,
            evidence_set=evidence_set,
            claims=[claim],
        )


class FakeSourceQualityEvaluator:
    """Evaluate one document deterministically."""

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        return ResearchSourceQualityEvaluation(
            document=document,
            evaluator="fake-source-quality",
            authority_score=0.9,
            primary_source_score=0.8,
            recency_score=1.0,
            completeness_score=0.45,
            traceability_score=1.0,
            overall_score=0.77,
            quality_level=ResearchSourceQualityLevel.HIGH,
        )


def request() -> ResearchRequest:
    """Return one E2E research request."""

    return ResearchRequest(
        request_id="research-001",
        question=(
            "How does agent memory support AI systems?"
        ),
        objective=(
            "Explain agent memory using traceable evidence."
        ),
    )


def pipeline(
    *,
    source_searcher: object | None = None,
) -> SingleResearchAgentPipeline:
    """Return one fully configured test pipeline."""

    return SingleResearchAgentPipeline(
        request_validator=FakeRequestValidator(),
        task_decomposer=FakeTaskDecomposer(),
        query_planner=FakeQueryPlanner(),
        source_searcher=(
            source_searcher
            if source_searcher is not None
            else FakeSourceSearcher()
        ),
        source_reader=FakeSourceReader(),
        evidence_extractor=FakeEvidenceExtractor(),
        claim_builder=FakeClaimBuilder(),
        source_quality_evaluator=(
            FakeSourceQualityEvaluator()
        ),
    )


def test_pipeline_runs_end_to_end() -> None:
    result = pipeline().run(request())

    assert result.workspace.stage is (
        ResearchWorkspaceStage.CLAIMS_BUILT
    )
    assert result.workspace.progress().task_count == 1
    assert result.workspace.progress().query_count == 1
    assert (
        result.workspace.progress().candidate_count
        == 1
    )
    assert (
        result.workspace.progress().document_count
        == 1
    )
    assert (
        result.workspace.progress().evidence_count
        == 1
    )
    assert result.workspace.progress().claim_count == 1


def test_pipeline_builds_report_and_quality() -> None:
    result = pipeline().run(request())

    assert result.report.claim_count == 1
    assert result.report.citation_count == 1
    assert result.report.source_count == 1
    assert result.quality.claim_coverage_score == 1.0
    assert result.quality.citation_coverage_score == 1.0
    assert result.quality.passed is True


def test_pipeline_uses_default_workspace_id() -> None:
    result = pipeline().run(request())

    assert result.workspace.workspace_id == (
        "research-001-workspace"
    )


def test_pipeline_accepts_custom_workspace_id() -> None:
    result = pipeline().run(
        request(),
        workspace_id="custom-workspace",
    )

    assert result.workspace.workspace_id == (
        "custom-workspace"
    )


def test_pipeline_rejects_blank_workspace_id() -> None:
    with pytest.raises(
        ResearchPipelineError,
        match="workspace_id must not be blank",
    ):
        pipeline().run(
            request(),
            workspace_id=" ",
        )


def test_pipeline_rejects_empty_search_result() -> None:
    value = pipeline(
        source_searcher=EmptySourceSearcher()
    )

    with pytest.raises(
        ResearchPipelineError,
        match=(
            "source search produced no candidates"
        ),
    ):
        value.run(request())


def test_pipeline_is_deterministic() -> None:
    value = pipeline()

    first = value.run(request())
    second = value.run(request())

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
