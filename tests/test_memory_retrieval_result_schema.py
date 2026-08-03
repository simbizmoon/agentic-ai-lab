"""Tests for end-to-end memory retrieval result schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.memory_context import (
    MemoryContext,
    MemoryContextItem,
)
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_retrieval_result import (
    MemoryRetrievalResult,
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


def search_result(
    memory_id: str,
) -> MemorySearchResult:
    """Return one valid ranked search result."""

    memory = MemoryRecord(
        memory_id=memory_id,
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

    return MemorySearchResult(
        memory=memory,
        score=0.8,
        matched_terms=["commands"],
        breakdown=MemoryScoreBreakdown(
            content_overlap=1.0,
            tag_overlap=0.0,
            phrase_match=0.0,
            importance=0.8,
            confidence=1.0,
        ),
    )


def context(
    memory_id: str,
) -> MemoryContext:
    """Return context containing one memory."""

    return MemoryContext(
        query="verified commands",
        items=[
            MemoryContextItem(
                memory_id=memory_id,
                content=(
                    "The user prefers verified commands."
                ),
                score=0.8,
            )
        ],
        rendered_text="<memory_context />",
    )


def test_result_accepts_consistent_values() -> None:
    result = MemoryRetrievalResult(
        search_results=[
            search_result("mem-001")
        ],
        context=context("mem-001"),
        retrieved_memory_ids=["mem-001"],
        access_recorded=False,
    )

    assert result.retrieved_memory_ids == [
        "mem-001"
    ]


def test_result_rejects_duplicate_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="must be unique",
    ):
        MemoryRetrievalResult(
            search_results=[
                search_result("mem-001")
            ],
            context=context("mem-001"),
            retrieved_memory_ids=[
                "mem-001",
                "mem-001",
            ],
            access_recorded=False,
        )


def test_result_rejects_id_not_in_search_results() -> None:
    with pytest.raises(
        ValidationError,
        match="must come from search results",
    ):
        MemoryRetrievalResult(
            search_results=[
                search_result("mem-001")
            ],
            context=context("mem-002"),
            retrieved_memory_ids=["mem-002"],
            access_recorded=False,
        )


def test_result_rejects_context_id_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="must match context items",
    ):
        MemoryRetrievalResult(
            search_results=[
                search_result("mem-001"),
                search_result("mem-002"),
            ],
            context=context("mem-001"),
            retrieved_memory_ids=["mem-002"],
            access_recorded=False,
        )
