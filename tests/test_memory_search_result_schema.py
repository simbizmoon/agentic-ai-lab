"""Tests for ranked memory-search result schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_search_result import (
    MemoryScoreBreakdown,
    MemorySearchResult,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def memory() -> MemoryRecord:
    """Return one valid stored memory."""

    return MemoryRecord(
        memory_id="mem-001",
        kind=MemoryKind.SEMANTIC,
        scope=MemoryScope.USER,
        source=MemorySource.USER_STATEMENT,
        content="The user prefers verified commands.",
        subject_id="user-001",
        importance=0.8,
        confidence=1.0,
        created_at=NOW,
        updated_at=NOW,
    )


def breakdown() -> MemoryScoreBreakdown:
    """Return one valid score breakdown."""

    return MemoryScoreBreakdown(
        content_overlap=1.0,
        tag_overlap=0.0,
        phrase_match=1.0,
        importance=0.8,
        confidence=1.0,
    )


def test_result_accepts_valid_score() -> None:
    result = MemorySearchResult(
        memory=memory(),
        score=0.78,
        matched_terms=["commands", "verified"],
        breakdown=breakdown(),
    )

    assert result.score == 0.78


def test_result_rejects_duplicate_terms() -> None:
    with pytest.raises(
        ValidationError,
        match="matched terms must be unique",
    ):
        MemorySearchResult(
            memory=memory(),
            score=0.78,
            matched_terms=["Commands", "commands"],
            breakdown=breakdown(),
        )


def test_result_rejects_blank_term() -> None:
    with pytest.raises(
        ValidationError,
        match="matched terms must not be blank",
    ):
        MemorySearchResult(
            memory=memory(),
            score=0.78,
            matched_terms=["commands", " "],
            breakdown=breakdown(),
        )


def test_result_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        MemorySearchResult(
            memory=memory(),
            score=1.1,
            matched_terms=["commands"],
            breakdown=breakdown(),
        )
