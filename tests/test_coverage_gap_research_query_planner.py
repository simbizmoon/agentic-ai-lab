"""Tests for coverage-gap research query planning."""

import pytest

from app.research.coverage_gap_research_query_planner import (
    CoverageGapResearchQueryPlanner,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageLevel,
)
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQueryPriority,
    ResearchSearchQuerySet,
    ResearchSearchQueryType,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


def values() -> tuple[
    ResearchRequest,
    ResearchTaskGraph,
    ResearchSearchQuerySet,
    ResearchAnswerCoverageEvaluation,
]:
    request = ResearchRequest(
        request_id="research-001",
        question="How does tool calling work?",
        objective="Explain registration, invocation, and result handling.",
        maximum_sources=3,
    )
    graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id=request.request_id,
                title="Tool calling",
                question=request.question,
                objective=request.objective,
                completion_criteria=["Explain the mechanism"],
                expected_output="Mechanism description.",
            )
        ],
    )
    query_set = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="research-001-query-001",
                request_id=request.request_id,
                task_id="task-001",
                query_text="tool calling overview",
            )
        ],
    )
    coverage = ResearchAnswerCoverageEvaluation(
        evaluation_id="coverage-001",
        request_id=request.request_id,
        claim_ids=["claim-001"],
        coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
        coverage_score=0.4,
        covered_aspects=["Tools can be invoked."],
        missing_aspects=[
            "How tools are registered",
            "How calls are initiated",
            "How results return to execution",
        ],
        rationale="The concrete runtime mechanism is incomplete.",
    )
    return request, graph, query_set, coverage


def test_planner_targets_missing_aspects() -> None:
    request, graph, query_set, coverage = values()

    result = CoverageGapResearchQueryPlanner().plan(
        request=request,
        task_graph=graph,
        existing_query_set=query_set,
        coverage_evaluation=coverage,
    )

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_id == "research-001-query-coverage-001"
    assert query.query_type is ResearchSearchQueryType.FOCUSED
    assert query.priority is ResearchSearchQueryPriority.CRITICAL
    assert "How tools are registered" in query.query_text
    assert "How calls are initiated" in query.query_text
    assert "How results return to execution" in query.query_text
    assert query.metadata["reason"] == "answer_coverage_gap"
    assert query.metadata["replanning_round"] == "1"


def test_planner_is_deterministic() -> None:
    request, graph, query_set, coverage = values()
    planner = CoverageGapResearchQueryPlanner()

    first = planner.plan(
        request=request,
        task_graph=graph,
        existing_query_set=query_set,
        coverage_evaluation=coverage,
    )
    second = planner.plan(
        request=request,
        task_graph=graph,
        existing_query_set=query_set,
        coverage_evaluation=coverage,
    )

    assert first == second


def test_planner_requires_missing_aspects() -> None:
    request, graph, query_set, coverage = values()
    coverage = coverage.model_copy(
        update={"missing_aspects": []}
    )

    with pytest.raises(
        ValueError,
        match="must contain missing aspects",
    ):
        CoverageGapResearchQueryPlanner().plan(
            request=request,
            task_graph=graph,
            existing_query_set=query_set,
            coverage_evaluation=coverage,
        )
