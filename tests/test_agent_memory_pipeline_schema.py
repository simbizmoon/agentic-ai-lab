"""Tests for agent memory pipeline request schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_memory_pipeline import (
    AgentMemoryPipelineRequest,
)
from app.schemas.memory_retrieval import (
    MemoryRetrievalRequest,
)


def request(
    *,
    user_query: str = "How should commands be provided?",
    retrieval_query: str = (
        "How should commands be provided?"
    ),
) -> AgentMemoryPipelineRequest:
    """Return one valid pipeline request."""

    return AgentMemoryPipelineRequest(
        system_instructions=(
            "You are a careful research assistant."
        ),
        user_query=user_query,
        retrieval=MemoryRetrievalRequest(
            query=retrieval_query
        ),
    )


def test_request_accepts_matching_queries() -> None:
    value = request()

    assert value.user_query == value.retrieval.query


def test_request_rejects_different_queries() -> None:
    with pytest.raises(
        ValidationError,
        match="user_query must match retrieval query",
    ):
        request(
            user_query="Question one",
            retrieval_query="Question two",
        )


def test_request_ignores_surrounding_query_whitespace() -> None:
    value = request(
        user_query="  workflow question ",
        retrieval_query="workflow question",
    )

    assert value.user_query.strip() == (
        value.retrieval.query.strip()
    )


@pytest.mark.parametrize(
    "system_instructions",
    ["", " ", "\n\t"],
)
def test_request_rejects_blank_system_instructions(
    system_instructions: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="system instructions must not be blank",
    ):
        AgentMemoryPipelineRequest(
            system_instructions=system_instructions,
            user_query="Question",
            retrieval=MemoryRetrievalRequest(
                query="Question"
            ),
        )


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        AgentMemoryPipelineRequest(
            system_instructions="Instructions",
            user_query="Question",
            retrieval=MemoryRetrievalRequest(
                query="Question"
            ),
            unknown_value=True,
        )
