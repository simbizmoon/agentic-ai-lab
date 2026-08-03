"""Tests for memory deduplication schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.memory_deduplication import (
    MemoryDeduplicationAction,
    MemoryDeduplicationReason,
    MemoryDeduplicationResult,
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


def existing_memory() -> MemoryRecord:
    """Return one stored memory."""

    return MemoryRecord(
        memory_id="mem-001",
        kind=MemoryKind.SEMANTIC,
        scope=MemoryScope.USER,
        source=MemorySource.USER_STATEMENT,
        content="The user prefers verified commands.",
        subject_id="user-001",
        created_at=NOW,
        updated_at=NOW,
    )


def test_create_result_accepts_no_duplicate() -> None:
    result = MemoryDeduplicationResult(
        action=MemoryDeduplicationAction.CREATE,
        reasons=[
            MemoryDeduplicationReason.NO_DUPLICATE
        ],
        normalized_content="new fact",
    )

    assert result.matched_memory is None


def test_keep_existing_requires_match() -> None:
    result = MemoryDeduplicationResult(
        action=(
            MemoryDeduplicationAction.KEEP_EXISTING
        ),
        reasons=[
            MemoryDeduplicationReason.EXACT_DUPLICATE
        ],
        matched_memory=existing_memory(),
        normalized_content=(
            "the user prefers verified commands."
        ),
    )

    assert result.matched_memory is not None


def test_create_rejects_matched_memory() -> None:
    with pytest.raises(
        ValidationError,
        match="must not include matched_memory",
    ):
        MemoryDeduplicationResult(
            action=MemoryDeduplicationAction.CREATE,
            reasons=[
                MemoryDeduplicationReason.NO_DUPLICATE
            ],
            matched_memory=existing_memory(),
            normalized_content="new fact",
        )


def test_duplicate_action_requires_match() -> None:
    with pytest.raises(
        ValidationError,
        match="requires matched_memory",
    ):
        MemoryDeduplicationResult(
            action=(
                MemoryDeduplicationAction.UPDATE_EXISTING
            ),
            reasons=[
                MemoryDeduplicationReason
                .IMPORTANCE_INCREASED
            ],
            normalized_content="existing fact",
        )


def test_keep_existing_requires_exact_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires exact_duplicate reason",
    ):
        MemoryDeduplicationResult(
            action=(
                MemoryDeduplicationAction.KEEP_EXISTING
            ),
            reasons=[
                MemoryDeduplicationReason
                .CONFIDENCE_INCREASED
            ],
            matched_memory=existing_memory(),
            normalized_content="existing fact",
        )
