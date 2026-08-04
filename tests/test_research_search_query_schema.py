"""Tests for research search query schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.research_request import ResearchSourceType
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


def task(
    *,
    task_id: str,
    request_id: str = "research-001",
) -> ResearchTask:
    """Return one valid research task."""

    return ResearchTask(
        task_id=task_id,
        request_id=request_id,
        title=f"Investigate {task_id}",
        question=f"What should {task_id} investigate?",
        objective=(
            f"Produce verified findings for {task_id}."
        ),
        completion_criteria=[
            "Produce one supported finding"
        ],
        expected_output="Structured findings.",
    )


def graph() -> ResearchTaskGraph:
    """Return one valid task graph."""

    return ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            task(task_id="task-a"),
            task(task_id="task-b"),
        ],
    )


def query(
    *,
    query_id: str = "query-001",
    task_id: str = "task-a",
    request_id: str = "research-001",
    query_text: str = (
        "agent memory architecture primary research"
    ),
    **overrides: object,
) -> ResearchSearchQuery:
    """Return one valid research search query."""

    values: dict[str, object] = {
        "query_id": query_id,
        "request_id": request_id,
        "task_id": task_id,
        "query_text": query_text,
        "query_type": (
            ResearchSearchQueryType.PRIMARY_SOURCE
        ),
        "priority": (
            ResearchSearchQueryPriority.HIGH
        ),
        "preferred_source_types": [
            ResearchSourceType.PRIMARY_RESEARCH,
        ],
        "start_date": date(2024, 1, 1),
        "end_date": date(2026, 12, 31),
        "maximum_results": 20,
        "exact_phrase": False,
        "metadata": {
            "planner": "single-agent",
        },
    }
    values.update(overrides)

    return ResearchSearchQuery.model_validate(values)


def test_query_accepts_valid_values() -> None:
    value = query()

    assert value.query_id == "query-001"
    assert value.priority is (
        ResearchSearchQueryPriority.HIGH
    )
    assert value.maximum_results == 20


def test_query_uses_safe_defaults() -> None:
    value = ResearchSearchQuery(
        query_id="query-001",
        request_id="research-001",
        task_id="task-a",
        query_text="agent memory architecture",
    )

    assert value.query_type is (
        ResearchSearchQueryType.FOCUSED
    )
    assert value.priority is (
        ResearchSearchQueryPriority.MEDIUM
    )
    assert value.maximum_results == 10
    assert value.exact_phrase is False


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("query_id", " "),
        ("request_id", ""),
        ("task_id", "\t"),
        ("query_text", "\n"),
    ],
)
def test_query_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    values: dict[str, object] = {
        "query_id": "query-001",
        "request_id": "research-001",
        "task_id": "task-a",
        "query_text": "agent memory architecture",
    }
    values[field_name] = field_value

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        ResearchSearchQuery.model_validate(values)


def test_query_rejects_duplicate_source_types() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "preferred_source_types must not "
            "contain duplicates"
        ),
    ):
        query(
            preferred_source_types=[
                ResearchSourceType.ACADEMIC,
                ResearchSourceType.ACADEMIC,
            ]
        )


def test_query_rejects_reversed_dates() -> None:
    with pytest.raises(
        ValidationError,
        match="start_date must not be after end_date",
    ):
        query(
            start_date=date(2026, 1, 1),
            end_date=date(2025, 1, 1),
        )


def test_query_rejects_invalid_result_limit() -> None:
    with pytest.raises(ValidationError):
        query(maximum_results=0)

    with pytest.raises(ValidationError):
        query(maximum_results=101)


def test_query_normalizes_search_text() -> None:
    value = query(
        query_text=(
            "  Agent   Memory Architecture  "
        )
    )

    assert value.normalized_query_text() == (
        "agent memory architecture"
    )


def test_query_set_accepts_valid_queries() -> None:
    value = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph(),
        queries=[
            query(),
            query(
                query_id="query-002",
                task_id="task-b",
                query_text="episodic agent memory",
            ),
        ],
    )

    assert len(value.queries) == 2


def test_query_set_rejects_duplicate_query_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="query IDs must be unique",
    ):
        ResearchSearchQuerySet(
            request_id="research-001",
            task_graph=graph(),
            queries=[
                query(query_id="query-001"),
                query(
                    query_id=" QUERY-001 ",
                    task_id="task-b",
                    query_text="different query",
                ),
            ],
        )


def test_query_set_rejects_mismatched_request_id() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all query request IDs must match"
        ),
    ):
        ResearchSearchQuerySet(
            request_id="research-001",
            task_graph=graph(),
            queries=[
                query(request_id="research-002"),
            ],
        )


def test_query_set_rejects_missing_task_reference() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all queries must reference existing tasks"
        ),
    ):
        ResearchSearchQuerySet(
            request_id="research-001",
            task_graph=graph(),
            queries=[
                query(task_id="missing-task"),
            ],
        )


def test_query_set_rejects_duplicate_text_per_task() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "queries for the same task must not "
            "contain duplicate query text"
        ),
    ):
        ResearchSearchQuerySet(
            request_id="research-001",
            task_graph=graph(),
            queries=[
                query(
                    query_id="query-001",
                    query_text="Agent Memory",
                ),
                query(
                    query_id="query-002",
                    query_text=" agent   memory ",
                ),
            ],
        )


def test_query_set_allows_same_text_for_different_tasks() -> None:
    value = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph(),
        queries=[
            query(
                query_id="query-001",
                task_id="task-a",
                query_text="Agent Memory",
            ),
            query(
                query_id="query-002",
                task_id="task-b",
                query_text=" agent memory ",
            ),
        ],
    )

    assert len(value.queries) == 2


def test_query_set_orders_by_priority_then_position() -> None:
    value = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph(),
        queries=[
            query(
                query_id="query-low",
                priority=(
                    ResearchSearchQueryPriority.LOW
                ),
            ),
            query(
                query_id="query-critical-a",
                task_id="task-b",
                query_text="critical query a",
                priority=(
                    ResearchSearchQueryPriority.CRITICAL
                ),
            ),
            query(
                query_id="query-critical-b",
                query_text="critical query b",
                priority=(
                    ResearchSearchQueryPriority.CRITICAL
                ),
            ),
        ],
    )

    assert [
        item.query_id
        for item in value.ordered_queries()
    ] == [
        "query-critical-a",
        "query-critical-b",
        "query-low",
    ]


def test_query_set_returns_queries_for_task() -> None:
    value = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph(),
        queries=[
            query(
                query_id="query-low",
                priority=(
                    ResearchSearchQueryPriority.LOW
                ),
            ),
            query(
                query_id="query-high",
                query_text="high priority query",
                priority=(
                    ResearchSearchQueryPriority.HIGH
                ),
            ),
            query(
                query_id="query-other",
                task_id="task-b",
                query_text="other task query",
            ),
        ],
    )

    assert [
        item.query_id
        for item in value.queries_for_task(" TASK-A ")
    ] == [
        "query-high",
        "query-low",
    ]


def test_query_set_rejects_blank_task_lookup() -> None:
    value = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph(),
        queries=[query()],
    )

    with pytest.raises(
        ValueError,
        match="task_id must not be blank",
    ):
        value.queries_for_task(" ")
