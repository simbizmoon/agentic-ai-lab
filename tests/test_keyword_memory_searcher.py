"""Tests for keyword-based memory retrieval."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.memory.clock import Clock
from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.keyword_memory_searcher import (
    KeywordMemorySearcher,
)
from app.memory.memory_service import MemoryService
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_search import (
    MemorySearchRequest,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed UTC timestamp."""

    def now(self) -> datetime:
        return NOW


def memory(
    *,
    memory_id: str,
    content: str,
    subject_id: str = "user-001",
    tags: list[str] | None = None,
    importance: float = 0.5,
    confidence: float = 1.0,
    created_at: datetime = NOW,
    updated_at: datetime = NOW,
    expires_at: datetime | None = None,
) -> MemoryRecord:
    """Return one stored semantic user memory."""

    return MemoryRecord(
        memory_id=memory_id,
        kind=MemoryKind.SEMANTIC,
        scope=MemoryScope.USER,
        source=MemorySource.USER_STATEMENT,
        content=content,
        subject_id=subject_id,
        tags=tags or [],
        importance=importance,
        confidence=confidence,
        created_at=created_at,
        updated_at=updated_at,
        expires_at=expires_at,
    )


def make_searcher(
    *memories: MemoryRecord,
) -> KeywordMemorySearcher:
    """Create a searcher containing supplied memories."""

    store = InMemoryMemoryStore()

    for stored_memory in memories:
        store.add(stored_memory)

    service = MemoryService(
        store=store,
        clock=FixedClock(),
    )

    return KeywordMemorySearcher(
        memory_service=service
    )


def test_search_returns_most_relevant_first() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content=(
                "The user prefers verified commands."
            ),
            importance=0.8,
        ),
        memory(
            memory_id="mem-002",
            content="The project uses PostgreSQL.",
            importance=0.9,
        ),
    )

    results = searcher.search(
        MemorySearchRequest(
            query="verified commands",
            minimum_score=0.1,
        )
    )

    assert results[0].memory.memory_id == "mem-001"
    assert results[0].matched_terms == [
        "commands",
        "verified",
    ]


def test_search_applies_subject_filter() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-user-1",
            content="The user prefers dark mode.",
            subject_id="user-001",
        ),
        memory(
            memory_id="mem-user-2",
            content="The user prefers dark mode.",
            subject_id="user-002",
        ),
    )

    results = searcher.search(
        MemorySearchRequest(
            query="dark mode",
            subject_id="user-002",
        )
    )

    assert [
        result.memory.memory_id
        for result in results
    ] == ["mem-user-2"]


def test_search_respects_limit() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content="workflow one",
        ),
        memory(
            memory_id="mem-002",
            content="workflow two",
        ),
        memory(
            memory_id="mem-003",
            content="workflow three",
        ),
    )

    results = searcher.search(
        MemorySearchRequest(
            query="workflow",
            limit=2,
        )
    )

    assert len(results) == 2


def test_search_excludes_below_minimum_score() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content="The project uses PostgreSQL.",
            importance=0.5,
            confidence=1.0,
        )
    )

    results = searcher.search(
        MemorySearchRequest(
            query="vibration motor",
            minimum_score=0.2,
        )
    )

    assert results == []


def test_search_uses_tags() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content="The user has a preference.",
            tags=["workflow"],
        )
    )

    results = searcher.search(
        MemorySearchRequest(
            query="workflow",
            minimum_score=0.2,
        )
    )

    assert results[0].breakdown.tag_overlap == 1.0


def test_search_excludes_expired_memory() -> None:
    searcher = make_searcher(
        memory(
            memory_id="expired",
            content="verified commands",
            created_at=NOW - timedelta(days=2),
            updated_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
        ),
        memory(
            memory_id="active",
            content="verified commands",
        ),
    )

    results = searcher.search(
        MemorySearchRequest(
            query="verified commands",
        )
    )

    assert [
        result.memory.memory_id
        for result in results
    ] == ["active"]


def test_search_can_include_expired_memory() -> None:
    searcher = make_searcher(
        memory(
            memory_id="expired",
            content="verified commands",
            created_at=NOW - timedelta(days=2),
            updated_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
        )
    )

    results = searcher.search(
        MemorySearchRequest(
            query="verified commands",
            include_expired=True,
        )
    )

    assert [
        result.memory.memory_id
        for result in results
    ] == ["expired"]


def test_search_result_order_is_deterministic() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-b",
            content="workflow",
            importance=0.5,
        ),
        memory(
            memory_id="mem-a",
            content="workflow",
            importance=0.5,
        ),
    )

    results = searcher.search(
        MemorySearchRequest(query="workflow")
    )

    assert [
        result.memory.memory_id
        for result in results
    ] == [
        "mem-a",
        "mem-b",
    ]


def test_search_does_not_modify_access_time() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content="verified commands",
        )
    )

    searcher.search(
        MemorySearchRequest(
            query="verified commands"
        )
    )

    stored = searcher.memory_service.store.get(
        "mem-001"
    )

    assert stored.last_accessed_at is None


def test_store_query_can_still_be_used_directly() -> None:
    searcher = make_searcher(
        memory(
            memory_id="mem-001",
            content="verified commands",
        )
    )

    memories = searcher.memory_service.list(
        query=MemoryQuery(
            subject_id="user-001"
        )
    )

    assert len(memories) == 1
