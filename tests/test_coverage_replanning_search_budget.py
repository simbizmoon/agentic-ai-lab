"""Budget-bound behavior tests for coverage-guided replanning."""

from __future__ import annotations

from collections import deque

from app.research.coverage_gap_research_query_planner import (
    CoverageGapResearchQueryPlanner,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceSearchAdapter,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.research.supplemental_research_query_planner import (
    SupplementalResearchQueryPlanner,
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
from app.schemas.research_search_budget import (
    ResearchSearchBudget,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchResult,
    ResearchSourceSearchStatus,
)
from tests.test_single_research_agent_pipeline import (
    BackfillEvidenceExtractor,
    FakeQueryPlanner,
    FakeRequestValidator,
    FakeSourceQualityEvaluator,
    FakeTaskDecomposer,
    OrderedBackfillSelector,
    ReplanningSourceReader,
)


class CoverageSequenceEvaluator:
    """Return one or more deterministic coverage evaluations."""

    def __init__(
        self,
        levels: list[AnswerCoverageLevel],
    ) -> None:
        self._levels = deque(levels)
        self.calls = 0

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> ResearchAnswerCoverageEvaluation:
        self.calls += 1

        if not self._levels:
            raise AssertionError(
                "coverage evaluator called too many times"
            )

        level = self._levels.popleft()

        return ResearchAnswerCoverageEvaluation(
            evaluation_id=f"coverage-{self.calls}",
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
            missing_aspects=(
                []
                if level is AnswerCoverageLevel.FULLY_COVERED
                else ["missing runtime detail"]
            ),
            rationale="Deterministic coverage judgment.",
        )


class ThreeRoundSearchTool:
    """Return deterministic candidates for initial, D-029, and coverage search."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "three-round-search"

    @property
    def provider(self) -> str:
        return "test-provider"

    def search(
        self,
        query: ResearchSearchQuery,
    ) -> ResearchSourceSearchResult:
        self.calls.append(query.query_id)

        if "coverage" in query.query_id:
            source_id = "source-e"
        elif "supplemental" in query.query_id:
            source_id = "source-d"
        else:
            source_id = "source-a"

        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=query.request_id,
            task_id=query.task_id,
            query_id=query.query_id,
            title=source_id,
            url=f"https://example.com/{source_id}",
            source_type=ResearchSourceType.ACADEMIC,
            rank=1,
        )

        return ResearchSourceSearchResult(
            query=query,
            status=ResearchSourceSearchStatus.SUCCEEDED,
            provider=self.provider,
            candidates=[candidate],
            error=None,
            duration_ms=10,
            metadata={
                "tool": self.name,
                "usage_credits": "1.0",
            },
        )


def request() -> ResearchRequest:
    return ResearchRequest(
        request_id="research-001",
        question="How does the runtime mechanism work?",
        objective="Explain the complete runtime mechanism.",
        maximum_sources=3,
    )


def build_pipeline(
    *,
    budget: ResearchSearchBudget,
    coverage_levels: list[AnswerCoverageLevel],
) -> tuple[
    SingleResearchAgentPipeline,
    ThreeRoundSearchTool,
    CoverageSequenceEvaluator,
]:
    tool = ThreeRoundSearchTool()
    searcher = PipelineSourceSearchAdapter(
        tool,
        maximum_candidates=9,
        minimum_results_per_query=9,
        budget=budget,
    )
    evaluator = CoverageSequenceEvaluator(
        coverage_levels
    )

    pipeline = SingleResearchAgentPipeline(
        request_validator=FakeRequestValidator(),
        task_decomposer=FakeTaskDecomposer(),
        query_planner=FakeQueryPlanner(),
        source_searcher=searcher,
        source_reader=ReplanningSourceReader(),
        evidence_extractor=BackfillEvidenceExtractor(
            {"source-a", "source-d", "source-e"}
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=FakeSourceQualityEvaluator(),
        document_selector=OrderedBackfillSelector(),
        supplemental_query_planner=(
            SupplementalResearchQueryPlanner()
        ),
        answer_coverage_evaluator=evaluator,
        coverage_gap_query_planner=(
            CoverageGapResearchQueryPlanner()
        ),
    )

    return pipeline, tool, evaluator


def test_coverage_retry_is_blocked_when_search_budget_is_exhausted() -> None:
    pipeline, tool, evaluator = build_pipeline(
        budget=ResearchSearchBudget(
            maximum_provider_calls=2,
            maximum_credits=2.0,
            maximum_latency_ms=100,
        ),
        coverage_levels=[
            AnswerCoverageLevel.PARTIALLY_COVERED,
        ],
    )

    result = pipeline.run(request())

    assert evaluator.calls == 1
    assert tool.calls == [
        "query-001",
        "research-001-query-supplemental-001",
    ]

    metadata = result.workspace.metadata

    assert (
        metadata["coverage_replanning_triggered"]
        == "true"
    )
    assert (
        metadata["coverage_replanning_attempt_count"]
        == "1"
    )
    assert (
        metadata["coverage_replanning_blocked_by_budget"]
        == "true"
    )
    assert metadata[
        "coverage_replanning_claims_rebuilt"
    ] == "false"
    assert metadata[
        "coverage_final_level"
    ] == "partially_covered"
    assert metadata["search_provider_call_limit"] == "2"
    assert metadata["search_provider_call_count"] == "2"
    assert metadata["search_blocked_query_count"] == "1"


def test_initial_d029_and_coverage_retry_use_at_most_three_provider_calls() -> None:
    pipeline, tool, evaluator = build_pipeline(
        budget=ResearchSearchBudget(
            maximum_provider_calls=3,
            maximum_credits=3.0,
            maximum_latency_ms=100,
        ),
        coverage_levels=[
            AnswerCoverageLevel.PARTIALLY_COVERED,
            AnswerCoverageLevel.FULLY_COVERED,
        ],
    )

    result = pipeline.run(request())

    assert evaluator.calls == 2
    assert tool.calls == [
        "query-001",
        "research-001-query-supplemental-001",
        "research-001-query-coverage-001",
    ]

    metadata = result.workspace.metadata

    assert metadata["search_provider_call_limit"] == "3"
    assert metadata["search_provider_call_count"] == "3"
    assert metadata["search_blocked_query_count"] == "0"
    assert (
        metadata["coverage_replanning_attempt_count"]
        == "1"
    )
    assert (
        metadata["coverage_replanning_claims_rebuilt"]
        == "true"
    )
    assert metadata["coverage_initial_level"] == (
        "partially_covered"
    )
    assert metadata["coverage_final_level"] == (
        "fully_covered"
    )
