"""Tests for memory query filters."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def test_query_accepts_valid_filters() -> None:
    query = MemoryQuery(
        kinds=[MemoryKind.SEMANTIC],
        scopes=[MemoryScope.USER],
        subject_id="user-001",
        tags=["preference"],
        minimum_importance=0.7,
        created_after=NOW - timedelta(days=1),
        created_before=NOW,
    )

    assert query.subject_id == "user-001"
    assert query.minimum_importance == 0.7


def test_query_rejects_blank_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match="subject_id must not be blank",
    ):
        MemoryQuery(subject_id="   ")


def test_query_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="query tags must be unique",
    ):
        MemoryQuery(
            tags=["Preference", "preference"]
        )


def test_query_rejects_naive_datetime() -> None:
    with pytest.raises(
        ValidationError,
        match="created_after must be timezone-aware",
    ):
        MemoryQuery(
            created_after=NOW.replace(tzinfo=None)
        )


def test_query_rejects_reversed_date_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "created_after must not be later "
            "than created_before"
        ),
    ):
        MemoryQuery(
            created_after=NOW,
            created_before=NOW - timedelta(days=1),
        )


def test_query_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MemoryQuery(unknown_field=True)
