"""Tests for agent memory context schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.memory_context import (
    MemoryContext,
    MemoryContextItem,
)


def item() -> MemoryContextItem:
    """Return one valid memory context item."""

    return MemoryContextItem(
        memory_id="mem-001",
        content="The user prefers commands.",
        score=0.8,
        tags=["preference"],
    )


def test_context_accepts_valid_values() -> None:
    context = MemoryContext(
        query="verified commands",
        items=[item()],
        rendered_text="<memory_context />",
    )

    assert context.omitted_count == 0
    assert context.was_truncated is False


def test_item_rejects_blank_memory_id() -> None:
    with pytest.raises(
        ValidationError,
        match="memory_id",
    ):
        MemoryContextItem(
            memory_id=" ",
            content="Memory content.",
            score=0.8,
        )


def test_item_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="tags must be unique",
    ):
        MemoryContextItem(
            memory_id="mem-001",
            content="Memory content.",
            score=0.8,
            tags=["Preference", "preference"],
        )


def test_context_rejects_inconsistent_truncation() -> None:
    with pytest.raises(
        ValidationError,
        match="truncation fields are inconsistent",
    ):
        MemoryContext(
            query="workflow",
            items=[item()],
            rendered_text="<memory_context />",
            omitted_count=1,
            was_truncated=False,
        )


def test_context_rejects_blank_query() -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        MemoryContext(
            query=" ",
            items=[],
            rendered_text="<memory_context />",
        )
