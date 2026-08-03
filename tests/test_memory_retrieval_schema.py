"""Tests for memory retrieval request schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
)
from app.schemas.memory_retrieval import (
    MemoryRetrievalRequest,
)


def test_request_accepts_valid_values() -> None:
    request = MemoryRetrievalRequest(
        query="verified commands",
        search_limit=10,
        context_limit=3,
        minimum_search_score=0.2,
        minimum_context_score=0.4,
        kinds=[MemoryKind.SEMANTIC],
        scopes=[MemoryScope.USER],
        subject_id="user-001",
    )

    assert request.search_limit == 10
    assert request.context_limit == 3


@pytest.mark.parametrize(
    "query",
    ["", " ", "\n\t"],
)
def test_request_rejects_blank_query(
    query: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        MemoryRetrievalRequest(query=query)


def test_request_rejects_context_limit_above_search_limit() -> None:
    with pytest.raises(
        ValidationError,
        match="context_limit must not exceed",
    ):
        MemoryRetrievalRequest(
            query="workflow",
            search_limit=3,
            context_limit=4,
        )


def test_request_rejects_blank_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match="subject_id must not be blank",
    ):
        MemoryRetrievalRequest(
            query="workflow",
            subject_id=" ",
        )


def test_request_rejects_invalid_content_limit() -> None:
    with pytest.raises(ValidationError):
        MemoryRetrievalRequest(
            query="workflow",
            maximum_content_characters=49,
        )


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MemoryRetrievalRequest(
            query="workflow",
            unknown_value=True,
        )
