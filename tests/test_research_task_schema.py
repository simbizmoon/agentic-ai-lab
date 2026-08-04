"""Tests for research tasks and dependency graphs."""

import pytest
from pydantic import ValidationError

from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
    ResearchTaskPriority,
    ResearchTaskStatus,
)


def task(
    *,
    task_id: str,
    request_id: str = "research-001",
    depends_on: list[str] | None = None,
    **overrides: object,
) -> ResearchTask:
    """Return one valid research task."""

    values: dict[str, object] = {
        "task_id": task_id,
        "request_id": request_id,
        "title": f"Research task {task_id}",
        "question": f"What should {task_id} investigate?",
        "objective": (
            f"Produce verified findings for {task_id}."
        ),
        "priority": ResearchTaskPriority.MEDIUM,
        "status": ResearchTaskStatus.PLANNED,
        "depends_on": depends_on or [],
        "completion_criteria": [
            "At least one supported finding",
        ],
        "requires_search": True,
        "expected_output": (
            "A structured set of research findings."
        ),
        "metadata": {"owner": "single-agent"},
    }
    values.update(overrides)

    return ResearchTask.model_validate(values)


def valid_graph() -> ResearchTaskGraph:
    """Return one valid dependency graph."""

    return ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            task(task_id="task-a"),
            task(
                task_id="task-b",
                depends_on=["task-a"],
            ),
            task(
                task_id="task-c",
                depends_on=["task-a"],
            ),
            task(
                task_id="task-d",
                depends_on=["task-b", "task-c"],
            ),
        ],
    )


def test_task_accepts_valid_values() -> None:
    value = task(task_id="task-a")

    assert value.task_id == "task-a"
    assert value.priority is ResearchTaskPriority.MEDIUM
    assert value.status is ResearchTaskStatus.PLANNED
    assert value.requires_search is True


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("task_id", " "),
        ("request_id", ""),
        ("title", "\t"),
        ("question", " "),
        ("objective", ""),
        ("expected_output", "\n"),
    ],
)
def test_task_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    overrides: dict[str, object] = {
        field_name: field_value
    }

    if field_name == "task_id":
        with pytest.raises(
            ValidationError,
            match="task_id must not be blank",
        ):
            task(**overrides)
        return

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        task(
            task_id="task-a",
            **overrides,
        )


def test_task_requires_completion_criterion() -> None:
    with pytest.raises(ValidationError):
        task(
            task_id="task-a",
            completion_criteria=[],
        )


def test_task_rejects_blank_completion_criterion() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "completion_criteria must not contain "
            "blank values"
        ),
    ):
        task(
            task_id="task-a",
            completion_criteria=["valid", " "],
        )


def test_task_rejects_duplicate_completion_criteria() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "completion_criteria must not contain "
            "duplicates"
        ),
    ):
        task(
            task_id="task-a",
            completion_criteria=[
                "Verified source",
                " verified source ",
            ],
        )


def test_task_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        ValidationError,
        match="depends_on must not contain duplicates",
    ):
        task(
            task_id="task-b",
            depends_on=[
                "task-a",
                " TASK-A ",
            ],
        )


def test_task_rejects_self_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match="task must not depend on itself",
    ):
        task(
            task_id="task-a",
            depends_on=[" TASK-A "],
        )


def test_graph_accepts_valid_dependencies() -> None:
    graph = valid_graph()

    assert len(graph.tasks) == 4
    assert graph.root_task_ids() == ["task-a"]


def test_graph_returns_deterministic_topological_order() -> None:
    graph = valid_graph()

    assert graph.topological_order() == [
        "task-a",
        "task-b",
        "task-c",
        "task-d",
    ]


def test_graph_preserves_independent_task_order() -> None:
    graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            task(task_id="task-b"),
            task(task_id="task-a"),
            task(task_id="task-c"),
        ],
    )

    assert graph.topological_order() == [
        "task-b",
        "task-a",
        "task-c",
    ]


def test_graph_rejects_duplicate_task_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="task IDs must be unique",
    ):
        ResearchTaskGraph(
            request_id="research-001",
            tasks=[
                task(task_id="task-a"),
                task(task_id=" TASK-A "),
            ],
        )


def test_graph_rejects_mismatched_request_id() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all task request IDs must match "
            "the graph request_id"
        ),
    ):
        ResearchTaskGraph(
            request_id="research-001",
            tasks=[
                task(
                    task_id="task-a",
                    request_id="research-002",
                )
            ],
        )


def test_graph_rejects_missing_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all task dependencies must "
            "reference existing tasks"
        ),
    ):
        ResearchTaskGraph(
            request_id="research-001",
            tasks=[
                task(
                    task_id="task-a",
                    depends_on=["missing-task"],
                )
            ],
        )


def test_graph_rejects_dependency_cycle() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "research task graph must not "
            "contain cycles"
        ),
    ):
        ResearchTaskGraph(
            request_id="research-001",
            tasks=[
                task(
                    task_id="task-a",
                    depends_on=["task-b"],
                ),
                task(
                    task_id="task-b",
                    depends_on=["task-a"],
                ),
            ],
        )


def test_graph_requires_at_least_one_task() -> None:
    with pytest.raises(ValidationError):
        ResearchTaskGraph(
            request_id="research-001",
            tasks=[],
        )


def test_graph_is_frozen() -> None:
    graph = valid_graph()

    with pytest.raises(ValidationError):
        graph.request_id = "research-002"
