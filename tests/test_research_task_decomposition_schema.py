"""Tests for research task decomposition results."""

import pytest
from pydantic import ValidationError

from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)
from app.schemas.research_task_decomposition import (
    ResearchTaskDecompositionResult,
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
            "Compare memory patterns and explain their "
            "engineering trade-offs."
        ),
        include_topics=["working memory"],
        preferred_source_types=[
            ResearchSourceType.PRIMARY_RESEARCH
        ],
    )


def task(
    *,
    request_id: str = "research-001",
) -> ResearchTask:
    """Return one valid research task."""

    return ResearchTask(
        task_id=f"{request_id}-task-001",
        request_id=request_id,
        title="Investigate working memory",
        question="How does working memory differ?",
        objective=(
            "Produce verified findings about working memory."
        ),
        completion_criteria=[
            "Produce one verified finding"
        ],
        expected_output="Structured findings.",
    )


def test_result_accepts_consistent_values() -> None:
    value = request()
    validation = ResearchRequestValidator().validate(
        value
    )

    result = ResearchTaskDecompositionResult(
        request=value,
        validation=validation,
        task_graph=ResearchTaskGraph(
            request_id=value.request_id,
            tasks=[task()],
        ),
    )

    assert result.validation.valid is True
    assert len(result.task_graph.tasks) == 1


def test_result_rejects_mismatched_request_ids() -> None:
    value = request()
    validation = ResearchRequestValidator().validate(
        value
    )

    with pytest.raises(
        ValidationError,
        match=(
            "all decomposition request IDs must match"
        ),
    ):
        ResearchTaskDecompositionResult(
            request=value,
            validation=validation,
            task_graph=ResearchTaskGraph(
                request_id="research-002",
                tasks=[
                    task(request_id="research-002")
                ],
            ),
        )


def test_result_rejects_invalid_validation() -> None:
    invalid_request = request()
    invalid_request = invalid_request.model_copy(
        update={
            "question": "Short",
        }
    )
    validation = ResearchRequestValidator().validate(
        invalid_request
    )

    with pytest.raises(
        ValidationError,
        match=(
            "decomposition requires a valid "
            "research request"
        ),
    ):
        ResearchTaskDecompositionResult(
            request=invalid_request,
            validation=validation,
            task_graph=ResearchTaskGraph(
                request_id=invalid_request.request_id,
                tasks=[task()],
            ),
        )
