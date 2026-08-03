"""Tests for deterministic memory relevance scoring."""

from datetime import UTC, datetime

import pytest

from app.memory.memory_relevance_scorer import (
    MemoryRelevanceScorer,
)
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def memory(
    *,
    content: str = (
        "The user prefers verified commands."
    ),
    tags: list[str] | None = None,
    importance: float = 0.8,
    confidence: float = 1.0,
) -> MemoryRecord:
    """Return one stored memory."""

    return MemoryRecord(
        memory_id="mem-001",
        kind=MemoryKind.SEMANTIC,
        scope=MemoryScope.USER,
        source=MemorySource.USER_STATEMENT,
        content=content,
        subject_id="user-001",
        tags=tags or [],
        importance=importance,
        confidence=confidence,
        created_at=NOW,
        updated_at=NOW,
    )


def test_scores_full_content_and_phrase_match() -> None:
    result = MemoryRelevanceScorer().score(
        query="verified commands",
        memory=memory(),
    )

    assert result.breakdown.content_overlap == 1.0
    assert result.breakdown.phrase_match == 1.0
    assert result.matched_terms == [
        "commands",
        "verified",
    ]
    assert result.score == pytest.approx(0.78)


def test_scores_partial_content_overlap() -> None:
    result = MemoryRelevanceScorer().score(
        query="verified workflow",
        memory=memory(),
    )

    assert result.breakdown.content_overlap == 0.5
    assert result.breakdown.phrase_match == 0.0
    assert result.score == pytest.approx(0.405)


def test_scores_tag_overlap() -> None:
    result = MemoryRelevanceScorer().score(
        query="workflow",
        memory=memory(tags=["workflow"]),
    )

    assert result.breakdown.content_overlap == 0.0
    assert result.breakdown.tag_overlap == 1.0
    assert result.score == pytest.approx(0.33)


def test_unmatched_memory_retains_quality_score() -> None:
    result = MemoryRelevanceScorer().score(
        query="database",
        memory=memory(
            importance=0.8,
            confidence=1.0,
        ),
    )

    assert result.matched_terms == []
    assert result.score == pytest.approx(0.13)


def test_score_is_capped_at_one() -> None:
    result = MemoryRelevanceScorer().score(
        query="workflow",
        memory=memory(
            content="workflow",
            tags=["workflow"],
            importance=1.0,
            confidence=1.0,
        ),
    )

    assert result.score == 1.0
