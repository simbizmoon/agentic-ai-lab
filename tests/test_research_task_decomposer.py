"""Tests for deterministic research task decomposition."""

import pytest

from app.research.research_task_decomposer import (
    ResearchTaskDecomposer,
)
from app.research.research_task_decomposition_error import (
    ResearchTaskDecompositionError,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_request_validation import (
    ResearchRequestValidationCode,
)
from app.schemas.research_task import (
    ResearchTaskPriority,
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
        "depth": ResearchDepth.STANDARD,
        "include_topics": [
            "working memory",
            "episodic memory",
        ],
        "preferred_source_types": [
            ResearchSourceType.PRIMARY_RESEARCH,
        ],
        "maximum_sources": 10,
        "require_citations": True,
    }
    values.update(overrides)

    return ResearchRequest.model_validate(values)


def test_decomposer_builds_topic_and_synthesis_tasks() -> None:
    result = ResearchTaskDecomposer().decompose(
        request()
    )

    graph = result.task_graph

    assert [task.task_id for task in graph.tasks] == [
        "research-001-task-001",
        "research-001-task-002",
        "research-001-task-003",
    ]

    assert graph.root_task_ids() == [
        "research-001-task-001",
        "research-001-task-002",
    ]

    synthesis = graph.tasks[-1]

    assert synthesis.depends_on == [
        "research-001-task-001",
        "research-001-task-002",
    ]
    assert synthesis.requires_search is False
    assert synthesis.priority is (
        ResearchTaskPriority.CRITICAL
    )
    assert synthesis.metadata["task_type"] == (
        "synthesis"
    )


def test_decomposer_preserves_topic_order() -> None:
    result = ResearchTaskDecomposer().decompose(
        request(
            include_topics=[
                "semantic memory",
                "working memory",
                "episodic memory",
            ]
        )
    )

    topic_values = [
        task.metadata.get("topic")
        for task in result.task_graph.tasks[:-1]
    ]

    assert topic_values == [
        "semantic memory",
        "working memory",
        "episodic memory",
    ]


def test_single_topic_does_not_add_synthesis_task() -> None:
    result = ResearchTaskDecomposer().decompose(
        request(
            include_topics=["working memory"]
        )
    )

    assert len(result.task_graph.tasks) == 1
    assert (
        result.task_graph.tasks[0]
        .metadata["task_type"]
        == "topic_research"
    )


def test_request_without_topics_builds_general_task() -> None:
    result = ResearchTaskDecomposer().decompose(
        request(include_topics=[])
    )

    assert len(result.task_graph.tasks) == 1

    research_task = result.task_graph.tasks[0]

    assert research_task.task_id == (
        "research-001-task-001"
    )
    assert research_task.metadata["task_type"] == (
        "general_research"
    )
    assert research_task.requires_search is True


def test_decomposer_returns_validated_request() -> None:
    value = request()

    result = ResearchTaskDecomposer().decompose(value)

    assert result.request == value
    assert result.validation.valid is True
    assert result.task_graph.request_id == (
        value.request_id
    )


def test_decomposer_rejects_unready_request() -> None:
    value = request(question="Short")

    with pytest.raises(
        ResearchTaskDecompositionError
    ) as error:
        ResearchTaskDecomposer().decompose(value)

    assert error.value.validation.valid is False
    assert any(
        issue.code
        is ResearchRequestValidationCode
        .QUESTION_TOO_SHORT
        for issue in error.value.validation.issues
    )


def test_decomposer_error_lists_validation_codes() -> None:
    value = request(
        depth=ResearchDepth.DEEP,
        maximum_sources=2,
        require_citations=False,
    )

    with pytest.raises(
        ResearchTaskDecompositionError,
        match="deep_research_requires_citations",
    ):
        ResearchTaskDecomposer().decompose(value)


def test_decomposition_is_deterministic() -> None:
    decomposer = ResearchTaskDecomposer()
    value = request()

    first = decomposer.decompose(value)
    second = decomposer.decompose(value)

    assert first == second
    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
