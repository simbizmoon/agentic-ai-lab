"""Tests for research pipeline compatibility adapters."""

from __future__ import annotations

from app.research.pipeline_compatibility import (
    PipelineQueryPlannerAdapter,
    PipelineTaskDecomposerAdapter,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)


def request() -> ResearchRequest:
    """Return one valid request for adapter tests."""

    return ResearchRequest(
        request_id="compatibility-request-001",
        question=(
            "How does grounded research preserve evidence "
            "traceability?"
        ),
        objective=(
            "Explain how evidence and citations support a "
            "traceable grounded research report."
        ),
        include_topics=["evidence traceability"],
        preferred_source_types=[
            ResearchSourceType.OTHER,
        ],
        maximum_sources=4,
    )


def test_task_decomposer_adapter_returns_task_graph() -> None:
    research_request = request()

    task_graph = PipelineTaskDecomposerAdapter().decompose(
        research_request
    )

    assert task_graph.request_id == research_request.request_id
    assert len(task_graph.tasks) == 1
    assert task_graph.tasks[0].requires_search is True


def test_query_planner_adapter_returns_query_set() -> None:
    research_request = request()
    task_graph = PipelineTaskDecomposerAdapter().decompose(
        research_request
    )

    query_set = PipelineQueryPlannerAdapter().plan(
        request=research_request,
        task_graph=task_graph,
    )

    assert query_set.request_id == research_request.request_id
    assert query_set.task_graph == task_graph
    assert len(query_set.queries) == 1
    assert (
        query_set.queries[0].task_id
        == task_graph.tasks[0].task_id
    )


def test_adapters_can_be_used_in_sequence() -> None:
    research_request = request()
    decomposer = PipelineTaskDecomposerAdapter()
    planner = PipelineQueryPlannerAdapter()

    task_graph = decomposer.decompose(research_request)
    query_set = planner.plan(
        request=research_request,
        task_graph=task_graph,
    )

    assert query_set.queries
    assert all(
        query.request_id == research_request.request_id
        for query in query_set.queries
    )
