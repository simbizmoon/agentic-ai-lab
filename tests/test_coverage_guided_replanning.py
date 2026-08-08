"""Behavior tests for coverage-guided bounded replanning."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from app.research.coverage_gap_research_query_planner import (
    CoverageGapResearchQueryPlanner,
)
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageLevel,
)
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
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
from tests.test_single_research_agent_pipeline import (
    BackfillEvidenceExtractor,
    FakeQueryPlanner,
    FakeRequestValidator,
    FakeSourceQualityEvaluator,
    FakeTaskDecomposer,
    OrderedBackfillSelector,
)


class CoverageSequenceEvaluator:
    """Return coverage evaluations in a deterministic sequence."""

    def __init__(
        self,
        levels: list[AnswerCoverageLevel],
    ) -> None:
        self._levels = deque(levels)
        self.calls: list[list[str]] = []

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> ResearchAnswerCoverageEvaluation:
        self.calls.append(
            [claim.claim_id for claim in claim_set.claims]
        )

        if not self._levels:
            raise AssertionError(
                "coverage evaluator called too many times"
            )

        level = self._levels.popleft()

        missing = (
            []
            if level is AnswerCoverageLevel.FULLY_COVERED
            else ["runtime integration details"]
        )

        return ResearchAnswerCoverageEvaluation(
            evaluation_id=f"coverage-{len(self.calls)}",
            request_id=request.request_id,
            claim_ids=[
                claim.claim_id for claim in claim_set.claims
            ],
            coverage_level=level,
            coverage_score=(
                1.0
                if level is AnswerCoverageLevel.FULLY_COVERED
                else 0.5
            ),
            covered_aspects=["supported mechanism"],
            missing_aspects=missing,
            rationale="Deterministic test coverage judgment.",
        )



class IncrementalClaimGenerator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, evidence):
        self.calls.append(evidence.evidence_id)
        return SimpleNamespace(
            proposal=SimpleNamespace(
                text=f"Generated claim for {evidence.evidence_id}.",
                rationale="Deterministic incremental coverage test.",
            ),
            response_id=f"response-{evidence.evidence_id}",
            request_id=None,
            usage=None,
            elapsed_seconds=0.0,
        )


class CitationVerificationSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def verify(self, *, claim_set, evidence_set):
        self.calls.append(
            [claim.claim_id for claim in claim_set.claims]
        )
        return []


class ClaimRelevanceSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def evaluate(self, *, request, claim_set):
        self.calls.append(
            [claim.claim_id for claim in claim_set.claims]
        )
        return []


class CoverageSearch:
    """Return initial and optional coverage candidates."""

    def __init__(
        self,
        *,
        coverage_mode: str = "novel",
    ) -> None:
        self.coverage_mode = coverage_mode
        self.calls: list[str] = []

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        query = query_set.queries[0]
        self.calls.append(query.query_id)

        if "coverage" not in query.query_id:
            candidates = [
                self._candidate(
                    query=query,
                    source_id="source-a",
                    url="https://example.com/source-a",
                )
            ]
        elif self.coverage_mode == "novel":
            candidates = [
                self._candidate(
                    query=query,
                    source_id="source-d",
                    url="https://example.com/source-d",
                )
            ]
        elif self.coverage_mode == "duplicate":
            candidates = [
                self._candidate(
                    query=query,
                    source_id="source-a-duplicate",
                    url="https://example.com/source-a",
                )
            ]
        elif self.coverage_mode == "none":
            candidates = []
        else:
            raise AssertionError(
                f"unsupported coverage_mode={self.coverage_mode}"
            )

        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=candidates,
        )

    @staticmethod
    def _candidate(
        *,
        query,
        source_id: str,
        url: str,
    ) -> ResearchSourceCandidate:
        return ResearchSourceCandidate(
            source_id=source_id,
            request_id=query.request_id,
            task_id=query.task_id,
            query_id=query.query_id,
            title=source_id,
            url=url,
            source_type=ResearchSourceType.ACADEMIC,
            rank=1,
        )


class CoverageReader:
    """Return readable source documents."""

    def __init__(
        self,
        *,
        unreadable_coverage: bool = False,
    ) -> None:
        self.unreadable_coverage = unreadable_coverage
        self.calls: list[list[str]] = []

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        source_ids = [
            item.source_id for item in candidate_set.candidates
        ]
        self.calls.append(source_ids)

        documents = []
        for candidate in candidate_set.candidates:
            is_coverage = (
                "coverage" in candidate.query_id
            )

            if is_coverage and self.unreadable_coverage:
                continue

            content = f"Evidence from {candidate.source_id}."

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
                    reader="coverage-test-reader",
                )
            )

        return ResearchSourceDocumentSet(
            request_id=candidate_set.request_id,
            documents=documents,
        )


def coverage_request() -> ResearchRequest:
    return ResearchRequest(
        request_id="research-coverage-001",
        question="How does the runtime mechanism work?",
        objective="Explain the complete runtime mechanism.",
        maximum_sources=2,
    )


def coverage_pipeline(
    *,
    levels: list[AnswerCoverageLevel],
    coverage_mode: str = "novel",
    unreadable_coverage: bool = False,
    evidence_sources: set[str] | None = None,
) -> tuple[
    SingleResearchAgentPipeline,
    CoverageSearch,
    CoverageReader,
    CoverageSequenceEvaluator,
]:
    searcher = CoverageSearch(
        coverage_mode=coverage_mode
    )
    reader = CoverageReader(
        unreadable_coverage=unreadable_coverage
    )
    evaluator = CoverageSequenceEvaluator(levels)

    pipeline = SingleResearchAgentPipeline(
        request_validator=FakeRequestValidator(),
        task_decomposer=FakeTaskDecomposer(),
        query_planner=FakeQueryPlanner(),
        source_searcher=searcher,
        source_reader=reader,
        evidence_extractor=BackfillEvidenceExtractor(
            evidence_sources or {"source-a", "source-d"}
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=FakeSourceQualityEvaluator(),
        document_selector=OrderedBackfillSelector(),
        answer_coverage_evaluator=evaluator,
        coverage_gap_query_planner=(
            CoverageGapResearchQueryPlanner()
        ),
    )

    return pipeline, searcher, reader, evaluator



def test_coverage_replanning_reuses_downstream_results_incrementally() -> None:
    searcher = CoverageSearch()
    reader = CoverageReader()
    coverage_evaluator = CoverageSequenceEvaluator(
        [
            AnswerCoverageLevel.PARTIALLY_COVERED,
            AnswerCoverageLevel.FULLY_COVERED,
        ]
    )
    generator = IncrementalClaimGenerator()
    citation_spy = CitationVerificationSpy()
    relevance_spy = ClaimRelevanceSpy()

    pipeline = SingleResearchAgentPipeline(
        request_validator=FakeRequestValidator(),
        task_decomposer=FakeTaskDecomposer(),
        query_planner=FakeQueryPlanner(),
        source_searcher=searcher,
        source_reader=reader,
        evidence_extractor=BackfillEvidenceExtractor(
            {"source-a", "source-d"}
        ),
        claim_builder=GenerativePipelineClaimBuilder(
            generator=generator,
        ),
        source_quality_evaluator=FakeSourceQualityEvaluator(),
        document_selector=OrderedBackfillSelector(),
        semantic_citation_verifier=citation_spy,
        claim_relevance_evaluator=relevance_spy,
        answer_coverage_evaluator=coverage_evaluator,
        coverage_gap_query_planner=CoverageGapResearchQueryPlanner(),
    )

    result = pipeline.run(coverage_request())

    assert [
        claim.claim_id
        for claim in result.workspace.claim_set.claims
    ] == [
        "research-coverage-001-claim-001",
        "research-coverage-001-claim-002",
    ]
    assert len(generator.calls) == 2
    assert citation_spy.calls == [
        ["research-coverage-001-claim-001"],
        ["research-coverage-001-claim-002"],
    ]
    assert relevance_spy.calls == [
        ["research-coverage-001-claim-001"],
        ["research-coverage-001-claim-002"],
    ]
    assert coverage_evaluator.calls == [
        ["research-coverage-001-claim-001"],
        [
            "research-coverage-001-claim-001",
            "research-coverage-001-claim-002",
        ],
    ]

    metadata = result.workspace.metadata
    assert metadata["coverage_replanning_incremental_reuse"] == "true"
    assert metadata["coverage_replanning_incremental_claim_count"] == "1"
    assert metadata["coverage_replanning_claims_rebuilt"] == "true"


def test_fully_covered_does_not_trigger_coverage_replanning() -> None:
    pipeline, searcher, _, evaluator = coverage_pipeline(
        levels=[AnswerCoverageLevel.FULLY_COVERED]
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 1
    assert len(searcher.calls) == 1
    assert result.workspace.metadata[
        "coverage_replanning_triggered"
    ] == "false"
    assert result.workspace.metadata[
        "coverage_replanning_attempt_count"
    ] == "0"
    assert result.workspace.metadata[
        "coverage_initial_level"
    ] == "fully_covered"
    assert result.workspace.metadata[
        "coverage_final_level"
    ] == "fully_covered"


def test_partial_replans_once_and_can_become_fully_covered() -> None:
    pipeline, searcher, _, evaluator = coverage_pipeline(
        levels=[
            AnswerCoverageLevel.PARTIALLY_COVERED,
            AnswerCoverageLevel.FULLY_COVERED,
        ]
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 2
    assert len(searcher.calls) == 2
    assert result.workspace.metadata[
        "coverage_replanning_triggered"
    ] == "true"
    assert result.workspace.metadata[
        "coverage_replanning_attempt_count"
    ] == "1"
    assert result.workspace.metadata[
        "coverage_replanning_claims_rebuilt"
    ] == "true"
    assert result.workspace.metadata[
        "coverage_initial_level"
    ] == "partially_covered"
    assert result.workspace.metadata[
        "coverage_final_level"
    ] == "fully_covered"
    assert result.answer_coverage_evaluation is not None
    assert (
        result.answer_coverage_evaluation.coverage_level
        is AnswerCoverageLevel.FULLY_COVERED
    )


def test_insufficient_replans_once_and_stops_after_partial() -> None:
    pipeline, searcher, _, evaluator = coverage_pipeline(
        levels=[
            AnswerCoverageLevel.INSUFFICIENT,
            AnswerCoverageLevel.PARTIALLY_COVERED,
        ]
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 2
    assert len(searcher.calls) == 2
    assert result.workspace.metadata[
        "coverage_replanning_attempt_count"
    ] == "1"
    assert result.workspace.metadata[
        "coverage_initial_level"
    ] == "insufficient"
    assert result.workspace.metadata[
        "coverage_final_level"
    ] == "partially_covered"


def test_duplicate_only_coverage_search_preserves_initial_claims() -> None:
    pipeline, searcher, reader, evaluator = coverage_pipeline(
        levels=[AnswerCoverageLevel.PARTIALLY_COVERED],
        coverage_mode="duplicate",
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 1
    assert len(searcher.calls) == 2
    assert reader.calls == [["source-a"]]
    assert result.workspace.metadata[
        "coverage_replanning_novel_candidate_count"
    ] == "0"
    assert result.workspace.metadata[
        "coverage_replanning_claims_rebuilt"
    ] == "false"
    assert result.workspace.metadata[
        "coverage_final_level"
    ] == "partially_covered"


def test_unreadable_coverage_source_preserves_initial_claims() -> None:
    pipeline, searcher, reader, evaluator = coverage_pipeline(
        levels=[AnswerCoverageLevel.PARTIALLY_COVERED],
        unreadable_coverage=True,
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 1
    assert len(searcher.calls) == 2
    assert reader.calls == [
        ["source-a"],
        ["source-d"],
    ]
    assert result.workspace.metadata[
        "coverage_replanning_new_document_count"
    ] == "0"
    assert result.workspace.metadata[
        "coverage_replanning_claims_rebuilt"
    ] == "false"


def test_coverage_source_without_new_evidence_does_not_rebuild() -> None:
    pipeline, searcher, _, evaluator = coverage_pipeline(
        levels=[AnswerCoverageLevel.PARTIALLY_COVERED],
        evidence_sources={"source-a"},
    )

    result = pipeline.run(coverage_request())

    assert len(evaluator.calls) == 1
    assert len(searcher.calls) == 2
    assert result.workspace.metadata[
        "coverage_replanning_new_evidence_count"
    ] == "0"
    assert result.workspace.metadata[
        "coverage_replanning_claims_rebuilt"
    ] == "false"
