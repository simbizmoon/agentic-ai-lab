"""Tests for research search query planning results."""

import pytest
from pydantic import ValidationError

from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_search_query_planning import (
    ResearchSearchQueryPlanningResult,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


def request(
    *,
    request_id: str = "research-001",
) -> ResearchRequest:
    """Return one valid research request."""

    return ResearchRequest(
        request_id=request_id,
        question=(
            "How do agent memory architectures differ?"
        ),
        objective=(
            "Compare memory patterns and explain "
            "their engineering trade-offs."
        ),
    )


def graph(
    *,
    request_id: str = "research-001",
) -> ResearchTaskGraph:
    """Return one valid task graph."""

    return ResearchTaskGraph(
        request_id=request_id,
        tasks=[
            ResearchTask(
                task_id=f"{request_id}-task-001",
                request_id=request_id,
                title="Investigate memory",
                question="How does agent memory work?",
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


def query_set(
    *,
    task_graph: ResearchTaskGraph,
) -> ResearchSearchQuerySet:
    """Return one valid query set."""

    return ResearchSearchQuerySet(
        request_id=task_graph.request_id,
        task_graph=task_graph,
        queries=[
            ResearchSearchQuery(
                query_id=(
                    f"{task_graph.request_id}-query-001"
                ),
                request_id=task_graph.request_id,
                task_id=task_graph.tasks[0].task_id,
                query_text="agent memory architecture",
            )
        ],
    )


def test_result_accepts_consistent_values() -> None:
    value = request()
    task_graph = graph()

    result = ResearchSearchQueryPlanningResult(
        request=value,
        task_graph=task_graph,
        query_set=query_set(task_graph=task_graph),
    )

    assert result.request.request_id == "research-001"


def test_result_rejects_mismatched_request_ids() -> None:
    value = request()
    other_graph = graph(request_id="research-002")

    with pytest.raises(
        ValidationError,
        match=(
            "all search planning request IDs must match"
        ),
    ):
        ResearchSearchQueryPlanningResult(
            request=value,
            task_graph=other_graph,
            query_set=query_set(
                task_graph=other_graph
            ),
        )


def test_result_rejects_different_task_graph() -> None:
    value = request()
    task_graph = graph()

    different_graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="research-001-task-002",
                request_id="research-001",
                title="Different task",
                question="What differs?",
                objective=(
                    "Produce different verified findings."
                ),
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Different findings.",
            )
        ],
    )

    with pytest.raises(
        ValidationError,
        match=(
            "query set task graph must match "
            "the planning task graph"
        ),
    ):
        ResearchSearchQueryPlanningResult(
            request=value,
            task_graph=task_graph,
            query_set=query_set(
                task_graph=different_graph
            ),
        )
