"""Tests for bounded supplemental query planning."""

import pytest

from app.research.supplemental_research_query_planner import (
    SupplementalResearchQueryPlanner,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
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
]:
    """Return one request, task graph, and initial query set."""

    request = ResearchRequest(
        request_id="research-001",
        question="How does agent memory work?",
        objective="Explain agent memory with evidence.",
        maximum_sources=3,
    )

    graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id=request.request_id,
                title="Agent memory",
                question=request.question,
                objective=request.objective,
                completion_criteria=[
                    "Produce supported findings"
                ],
                expected_output="Supported findings.",
            )
        ],
    )

    initial = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="research-001-query-001",
                request_id=request.request_id,
                task_id="task-001",
                query_text="agent memory architecture",
            )
        ],
    )

    return request, graph, initial


def test_planner_creates_one_official_query() -> None:
    request, graph, initial = values()

    result = SupplementalResearchQueryPlanner().plan(
        request=request,
        task_graph=graph,
        initial_query_set=initial,
    )

    assert len(result.queries) == 1

    query = result.queries[0]

    assert query.query_id == (
        "research-001-query-supplemental-001"
    )
    assert (
        query.query_type
        is ResearchSearchQueryType.OFFICIAL
    )
    assert query.maximum_results == 9
    assert query.metadata == {
        "planner": "deterministic-supplemental",
        "reason": "low_source_diversity",
        "replanning_round": "1",
    }
    assert (
        ResearchSourceType.OFFICIAL_DOCUMENTATION
        in query.preferred_source_types
    )


def test_planner_does_not_duplicate_official_source_type() -> None:
    request, graph, initial = values()

    original_query = initial.queries[0].model_copy(
        update={
            "preferred_source_types": [
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            ]
        }
    )
    initial = initial.model_copy(
        update={"queries": [original_query]}
    )

    result = SupplementalResearchQueryPlanner().plan(
        request=request,
        task_graph=graph,
        initial_query_set=initial,
    )

    assert result.queries[0].preferred_source_types == [
        ResearchSourceType.OFFICIAL_DOCUMENTATION
    ]


def test_planner_avoids_duplicate_query_text() -> None:
    request, graph, initial = values()

    original_query = initial.queries[0].model_copy(
        update={
            "query_text": (
                "How does agent memory work? official guide"
            )
        }
    )
    initial = initial.model_copy(
        update={"queries": [original_query]}
    )

    result = SupplementalResearchQueryPlanner().plan(
        request=request,
        task_graph=graph,
        initial_query_set=initial,
    )

    assert result.queries[0].query_text == (
        "How does agent memory work? "
        "official guide concepts"
    )


def test_planner_rejects_mismatched_request_id() -> None:
    request, graph, initial = values()

    other_request = request.model_copy(
        update={"request_id": "research-002"}
    )

    with pytest.raises(
        ValueError,
        match="request_id must match",
    ):
        SupplementalResearchQueryPlanner().plan(
            request=other_request,
            task_graph=graph,
            initial_query_set=initial,
        )


def test_planner_is_deterministic() -> None:
    request, graph, initial = values()
    planner = SupplementalResearchQueryPlanner()

    first = planner.plan(
        request=request,
        task_graph=graph,
        initial_query_set=initial,
    )
    second = planner.plan(
        request=request,
        task_graph=graph,
        initial_query_set=initial,
    )

    assert first == second
    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
