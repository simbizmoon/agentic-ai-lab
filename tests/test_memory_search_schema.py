"""Tests for keyword memory-search request schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
)
from app.schemas.memory_search import (
    MemorySearchRequest,
)


def test_search_request_accepts_valid_values() -> None:
    request = MemorySearchRequest(
        query="verified commands",
        limit=3,
        minimum_score=0.2,
        kinds=[MemoryKind.SEMANTIC],
        scopes=[MemoryScope.USER],
        subject_id="user-001",
    )

    assert request.limit == 3
    assert request.minimum_score == 0.2


@pytest.mark.parametrize(
    "query",
    ["", "   ", "\n\t"],
)
def test_search_rejects_blank_query(
    query: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        MemorySearchRequest(query=query)


def test_search_rejects_blank_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match="subject_id must not be blank",
    ):
        MemorySearchRequest(
            query="workflow",
            subject_id=" ",
        )


def test_search_rejects_zero_limit() -> None:
    with pytest.raises(ValidationError):
        MemorySearchRequest(
            query="workflow",
            limit=0,
        )


def test_search_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        MemorySearchRequest(
            query="workflow",
            minimum_score=1.1,
        )


def test_search_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MemorySearchRequest(
            query="workflow",
            unknown_filter="value",
        )
