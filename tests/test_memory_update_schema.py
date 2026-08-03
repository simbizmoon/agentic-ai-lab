"""Tests for memory update values."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.memory_update import MemoryUpdate

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def test_update_accepts_mutable_values() -> None:
    update = MemoryUpdate(
        content="Updated memory content.",
        tags=["updated"],
        importance=0.9,
        last_accessed_at=NOW,
    )

    assert update.importance == 0.9


def test_update_rejects_no_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="must contain at least one field",
    ):
        MemoryUpdate()


def test_update_rejects_blank_content() -> None:
    with pytest.raises(
        ValidationError,
        match="memory content must not be blank",
    ):
        MemoryUpdate(content="   ")


def test_update_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="memory tags must be unique",
    ):
        MemoryUpdate(
            tags=["Project", "project"]
        )


def test_update_rejects_naive_datetime() -> None:
    with pytest.raises(
        ValidationError,
        match="expires_at must be timezone-aware",
    ):
        MemoryUpdate(
            expires_at=NOW.replace(tzinfo=None)
        )


def test_update_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MemoryUpdate(memory_id="not mutable")
