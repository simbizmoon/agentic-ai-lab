"""Tests for end-to-end agent memory retrieval."""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.clock import Clock
from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.keyword_memory_searcher import (
    KeywordMemorySearcher,
)
from app.memory.memory_retrieval_service import (
    MemoryRetrievalService,
)
from app.memory.memory_service import MemoryService
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_retrieval import (
    MemoryRetrievalRequest,
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
    """Return one fixed UTC time."""

    def now(self) -> datetime:
        return NOW


def memory(
    *,
    memory_id: str,
    content: str,
    tags: list[str] | None = None,
    importance: float = 0.5,
    confidence: float = 1.0,
    subject_id: str = "user-001",
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
        created_at=NOW,
        updated_at=NOW,
    )


def make_service(
    *memories: MemoryRecord,
) -> MemoryRetrievalService:
    """Return a deterministic retrieval service."""

    store = InMemoryMemoryStore()

    for stored_memory in memories:
        store.add(stored_memory)

    memory_service = MemoryService(
        store=store,
        clock=FixedClock(),
    )
    searcher = KeywordMemorySearcher(
        memory_service=memory_service
    )

    return MemoryRetrievalService(
        searcher=searcher
    )


def test_retrieve_returns_search_results_and_context() -> None:
    service = make_service(
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

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="verified commands",
            minimum_search_score=0.2,
            minimum_context_score=0.2,
        )
    )

    assert result.search_results[0].memory.memory_id == (
        "mem-001"
    )
    assert result.retrieved_memory_ids == [
        "mem-001"
    ]
    assert (
        "The user prefers verified commands."
        in result.context.rendered_text
    )


def test_context_limit_can_be_smaller_than_search_limit() -> None:
    service = make_service(
        memory(
            memory_id="mem-001",
            content="workflow alpha",
        ),
        memory(
            memory_id="mem-002",
            content="workflow beta",
        ),
        memory(
            memory_id="mem-003",
            content="workflow gamma",
        ),
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="workflow",
            search_limit=3,
            context_limit=2,
        )
    )

    assert len(result.search_results) == 3
    assert len(result.context.items) == 2
    assert result.context.omitted_count == 1


def test_context_score_can_be_stricter_than_search_score() -> None:
    service = make_service(
        memory(
            memory_id="strong",
            content="verified commands",
            importance=0.8,
        ),
        memory(
            memory_id="weak",
            content="unrelated database",
            importance=1.0,
            confidence=1.0,
        ),
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="verified commands",
            minimum_search_score=0.1,
            minimum_context_score=0.5,
        )
    )

    assert len(result.search_results) == 2
    assert result.retrieved_memory_ids == [
        "strong"
    ]


def test_retrieve_applies_subject_filter() -> None:
    service = make_service(
        memory(
            memory_id="user-1",
            content="The user prefers dark mode.",
            subject_id="user-001",
        ),
        memory(
            memory_id="user-2",
            content="The user prefers dark mode.",
            subject_id="user-002",
        ),
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="dark mode",
            subject_id="user-002",
        )
    )

    assert result.retrieved_memory_ids == [
        "user-2"
    ]


def test_retrieve_does_not_record_access_by_default() -> None:
    service = make_service(
        memory(
            memory_id="mem-001",
            content="verified commands",
        )
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="verified commands"
        )
    )

    stored = service.searcher.memory_service.store.get(
        "mem-001"
    )

    assert result.access_recorded is False
    assert stored.last_accessed_at is None


def test_retrieve_can_record_context_access() -> None:
    service = make_service(
        memory(
            memory_id="mem-001",
            content="verified commands",
        )
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="verified commands",
            record_access=True,
        )
    )

    stored = service.searcher.memory_service.store.get(
        "mem-001"
    )

    assert result.access_recorded is True
    assert stored.last_accessed_at == NOW


def test_only_context_items_have_access_recorded() -> None:
    service = make_service(
        memory(
            memory_id="mem-001",
            content="workflow alpha",
        ),
        memory(
            memory_id="mem-002",
            content="workflow beta",
        ),
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="workflow",
            search_limit=2,
            context_limit=1,
            record_access=True,
        )
    )

    selected_id = result.retrieved_memory_ids[0]
    unselected_id = (
        "mem-002"
        if selected_id == "mem-001"
        else "mem-001"
    )

    selected = (
        service.searcher.memory_service.store.get(
            selected_id
        )
    )
    unselected = (
        service.searcher.memory_service.store.get(
            unselected_id
        )
    )

    assert selected.last_accessed_at == NOW
    assert unselected.last_accessed_at is None


def test_retrieve_returns_empty_safe_context() -> None:
    service = make_service(
        memory(
            memory_id="mem-001",
            content="PostgreSQL database",
        )
    )

    result = service.retrieve(
        MemoryRetrievalRequest(
            query="vibration motor",
            minimum_search_score=0.5,
            minimum_context_score=0.5,
        )
    )

    assert result.search_results == []
    assert result.retrieved_memory_ids == []
    assert (
        "No relevant memory records were found."
        in result.context.rendered_text
    )
