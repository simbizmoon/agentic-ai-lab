"""End-to-end tests for the single research-agent pipeline."""

from datetime import date

import pytest

from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
)
from app.research.quality_aware_document_selector import (
    ResearchDocumentSelection,
)
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


BACKFILL_CONTENT = {
    "source-a": "Agent memory source A contains supported evidence.",
    "source-b": "Navigation-only source B.",
    "source-c": "Navigation-only source C.",
    "source-d": "Agent memory source D contains supported evidence.",
}


class BackfillSourceSearcher:
    """Produce four deterministic source candidates."""

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        candidates = [
            ResearchSourceCandidate(
                source_id=source_id,
                request_id=query_set.request_id,
                task_id="task-001",
                query_id="query-001",
                title=f"Agent memory {source_id}",
                url=f"https://example.com/{source_id}",
                source_type=ResearchSourceType.ACADEMIC,
                rank=position,
            )
            for position, source_id in enumerate(
                ("source-a", "source-b", "source-c", "source-d"),
                start=1,
            )
        ]
        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=candidates,
        )


class BackfillSourceReader:
    """Read every backfill candidate into one document set."""

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        documents = []
        for candidate in candidate_set.candidates:
            content = BACKFILL_CONTENT[candidate.source_id]
            documents.append(
                ResearchSourceDocument(
                    document_id=f"document-{candidate.source_id}",
                    candidate=candidate,
                    status=ResearchSourceDocumentStatus.READ,
                    content_type=ResearchSourceContentType.TEXT,
                    content=content,
                    language="en",
                    sections=[],
                    word_count=len(content.split()),
                    character_count=len(content),
                    reader="backfill-reader",
                )
            )
        return ResearchSourceDocumentSet(
            request_id=candidate_set.request_id,
            documents=documents,
        )


class OrderedBackfillSelector:
    """Return all documents in deterministic order."""

    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        del query_set
        evaluations = [
            evaluator.evaluate(document)
            for document in document_set.successful_documents()
        ]
        return ResearchDocumentSelection(
            document_set=document_set,
            evaluations=evaluations,
        )

    def rank(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        return self.select(
            document_set=document_set,
            evaluator=evaluator,
            query_set=query_set,
        )


class BackfillEvidenceExtractor:
    """Return evidence for configured sources and record calls."""

    def __init__(
        self,
        evidence_source_ids: set[str],
    ) -> None:
        self._evidence_source_ids = evidence_source_ids
        self.calls: list[str] = []

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        document = document_set.documents[0]
        source_id = document.candidate.source_id
        self.calls.append(source_id)

        if source_id not in self._evidence_source_ids:
            return ResearchEvidenceSet(
                request_id=document_set.request_id,
                document_set=document_set,
                evidence=[],
            )

        content = document.content
        evidence = ResearchEvidence(
            evidence_id=f"evidence-{source_id}",
            request_id=document_set.request_id,
            task_id=document.candidate.task_id,
            source_id=source_id,
            document_id=document.document_id,
            excerpt=content,
            start_character=0,
            end_character=len(content),
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


def backfill_request(
    *,
    maximum_sources: int,
) -> ResearchRequest:
    """Return a request with an explicit evidence-source limit."""

    return request().model_copy(
        update={"maximum_sources": maximum_sources}
    )


def backfill_pipeline(
    *,
    extractor: BackfillEvidenceExtractor,
) -> SingleResearchAgentPipeline:
    """Return a selector-enabled pipeline for backfill tests."""

    return SingleResearchAgentPipeline(
        request_validator=FakeRequestValidator(),
        task_decomposer=FakeTaskDecomposer(),
        query_planner=FakeQueryPlanner(),
        source_searcher=BackfillSourceSearcher(),
        source_reader=BackfillSourceReader(),
        evidence_extractor=extractor,
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=FakeSourceQualityEvaluator(),
        document_selector=OrderedBackfillSelector(),
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
def test_pipeline_backfills_no_evidence_documents() -> None:
    extractor = BackfillEvidenceExtractor({"source-a", "source-d"})

    result = backfill_pipeline(extractor=extractor).run(
        backfill_request(maximum_sources=2)
    )

    assert [
        document.candidate.source_id
        for document in result.workspace.document_set.documents
    ] == ["source-a", "source-d"]
    assert extractor.calls == [
        "source-a",
        "source-b",
        "source-c",
        "source-d",
    ]
    assert result.workspace.metadata == {
        "pipeline": "single-research-agent",
        "read_candidate_count": "4",
        "evidence_attempted_document_count": "4",
        "selected_document_count": "2",
        "evidence_source_count": "2",
        "backfilled_document_count": "2",
        "no_evidence_document_count": "2",
    }
    assert result.report.source_count == 2
    assert result.quality.passed is True


def test_pipeline_stops_after_reaching_source_quota() -> None:
    extractor = BackfillEvidenceExtractor(
        {"source-a", "source-b", "source-d"}
    )

    result = backfill_pipeline(extractor=extractor).run(
        backfill_request(maximum_sources=2)
    )

    assert extractor.calls == ["source-a", "source-b"]
    assert [
        document.candidate.source_id
        for document in result.workspace.document_set.documents
    ] == ["source-a", "source-b"]
    assert result.workspace.metadata[
        "evidence_attempted_document_count"
    ] == "2"


def test_pipeline_fails_quality_gate_when_candidates_are_exhausted() -> None:
    extractor = BackfillEvidenceExtractor({"source-a"})

    result = backfill_pipeline(extractor=extractor).run(
        backfill_request(maximum_sources=3)
    )

    assert extractor.calls == [
        "source-a",
        "source-b",
        "source-c",
        "source-d",
    ]
    assert result.report.source_count == 1
    assert result.quality.passed is False
    assert any(
        issue.code.value == "low_source_diversity"
        and issue.severity.value == "error"
        for issue in result.quality.issues
    )
    assert result.quality.metadata[
        "minimum_evidence_sources"
    ] == "2"
    assert result.quality.metadata[
        "actual_evidence_sources"
    ] == "1"


def test_pipeline_accepts_one_source_when_maximum_is_one() -> None:
    extractor = BackfillEvidenceExtractor({"source-a"})

    result = backfill_pipeline(extractor=extractor).run(
        backfill_request(maximum_sources=1)
    )

    assert extractor.calls == ["source-a"]
    assert result.report.source_count == 1
    assert result.quality.passed is True
    assert not any(
        issue.severity.value == "error"
        for issue in result.quality.issues
    )


def test_pipeline_backfill_is_deterministic() -> None:
    first_extractor = BackfillEvidenceExtractor(
        {"source-a", "source-d"}
    )
    second_extractor = BackfillEvidenceExtractor(
        {"source-a", "source-d"}
    )

    first = backfill_pipeline(extractor=first_extractor).run(
        backfill_request(maximum_sources=2)
    )
    second = backfill_pipeline(extractor=second_extractor).run(
        backfill_request(maximum_sources=2)
    )

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
    assert first_extractor.calls == second_extractor.calls
