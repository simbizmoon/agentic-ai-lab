"""Tests for deterministic research search query planning."""

import pytest

from app.research.research_search_query_planner import (
    ResearchSearchQueryPlanner,
)
from app.research.research_search_query_planning_error import (
    ResearchSearchQueryPlanningError,
)
from app.research.research_task_decomposer import (
    ResearchTaskDecomposer,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQueryType,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


def request(
    **overrides: object,
) -> ResearchRequest:
    """Return one valid research request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "question": (
            "How do agent memory architectures differ?"
        ),
        "objective": (
            "Compare major memory patterns and explain "
            "their engineering trade-offs."
        ),
        "include_topics": [
            "working memory",
            "episodic memory",
        ],
        "preferred_source_types": [
            ResearchSourceType.PRIMARY_RESEARCH,
            ResearchSourceType.OFFICIAL_DOCUMENTATION,
        ],
        "maximum_sources": 12,
    }
    values.update(overrides)

    return ResearchRequest.model_validate(values)


def task_graph(
    value: ResearchRequest,
) -> ResearchTaskGraph:
    """Decompose a request into a task graph."""

    return (
        ResearchTaskDecomposer()
        .decompose(value)
        .task_graph
    )


def test_planner_creates_queries_for_search_tasks() -> None:
    value = request()

    result = ResearchSearchQueryPlanner().plan(
        request=value,
        task_graph=task_graph(value),
    )

    assert len(result.query_set.queries) == 6

    assert {
        query.query_type
        for query in result.query_set.queries
    } == {
        ResearchSearchQueryType.FOCUSED,
        ResearchSearchQueryType.OFFICIAL,
        ResearchSearchQueryType.PRIMARY_SOURCE,
    }


def test_planner_skips_synthesis_task() -> None:
    value = request()
    graph = task_graph(value)

    synthesis_task = graph.tasks[-1]

    result = ResearchSearchQueryPlanner().plan(
        request=value,
        task_graph=graph,
    )

    assert synthesis_task.requires_search is False
    assert (
        result.query_set.queries_for_task(
            synthesis_task.task_id
        )
        == []
    )


def test_planner_generates_deterministic_ids() -> None:
    value = request()

    result = ResearchSearchQueryPlanner().plan(
        request=value,
        task_graph=task_graph(value),
    )

    assert [
        query.query_id
        for query in result.query_set.queries
    ] == [
        "research-001-query-001",
        "research-001-query-002",
        "research-001-query-003",
        "research-001-query-004",
        "research-001-query-005",
        "research-001-query-006",
    ]


def test_planner_inherits_request_constraints() -> None:
    value = request(
        maximum_sources=12,
    )

    result = ResearchSearchQueryPlanner().plan(
        request=value,
        task_graph=task_graph(value),
    )

    assert all(
        query.maximum_results == 6
        for query in result.query_set.queries
    )

    assert all(
        query.preferred_source_types
        == value.preferred_source_types
        for query in result.query_set.queries
    )


def test_planner_creates_only_focused_query_without_preferences() -> None:
    value = request(
        preferred_source_types=[],
    )

    result = ResearchSearchQueryPlanner().plan(
        request=value,
        task_graph=task_graph(value),
    )

    assert len(result.query_set.queries) == 2

    assert all(
        query.query_type
        is ResearchSearchQueryType.FOCUSED
        for query in result.query_set.queries
    )


def test_planner_rejects_mismatched_request_id() -> None:
    value = request()

    other_graph = ResearchTaskGraph(
        request_id="research-002",
        tasks=[
            ResearchTask(
                task_id="research-002-task-001",
                request_id="research-002",
                title="Investigate memory",
                question="How does memory work?",
                objective=(
                    "Produce verified memory findings."
                ),
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Structured findings.",
            )
        ],
    )

    with pytest.raises(
        ResearchSearchQueryPlanningError,
        match=(
            "request_id must match task graph request_id"
        ),
    ):
        ResearchSearchQueryPlanner().plan(
            request=value,
            task_graph=other_graph,
        )


def test_planner_rejects_graph_without_searchable_tasks() -> None:
    value = request(
        include_topics=["working memory"]
    )

    graph = ResearchTaskGraph(
        request_id=value.request_id,
        tasks=[
            ResearchTask(
                task_id="research-001-task-001",
                request_id=value.request_id,
                title="Synthesize findings",
                question=value.question,
                objective=value.objective,
                completion_criteria=[
                    "Produce a final synthesis"
                ],
                requires_search=False,
                expected_output="Final synthesis.",
            )
        ],
    )

    with pytest.raises(
        ResearchSearchQueryPlanningError,
        match=(
            "at least one searchable task"
        ),
    ):
        ResearchSearchQueryPlanner().plan(
            request=value,
            task_graph=graph,
        )


def test_planning_is_deterministic() -> None:
    value = request()
    graph = task_graph(value)
    planner = ResearchSearchQueryPlanner()

    first = planner.plan(
        request=value,
        task_graph=graph,
    )
    second = planner.plan(
        request=value,
        task_graph=graph,
    )

    assert first == second
    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
