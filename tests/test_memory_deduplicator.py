"""Tests for deterministic memory duplicate detection."""

from datetime import UTC, datetime, timedelta

from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.memory_deduplicator import (
    MemoryDeduplicator,
)
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_deduplication import (
    MemoryDeduplicationAction,
    MemoryDeduplicationReason,
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


def stored_memory(
    **overrides: object,
) -> MemoryRecord:
    """Return one stored memory."""

    values: dict[str, object] = {
        "memory_id": "mem-001",
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "tags": ["preference"],
        "importance": 0.5,
        "confidence": 0.8,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)

    return MemoryRecord(**values)


def request(
    **overrides: object,
) -> MemoryCreate:
    """Return one candidate memory."""

    values: dict[str, object] = {
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "tags": ["preference"],
        "importance": 0.5,
        "confidence": 0.8,
    }
    values.update(overrides)

    return MemoryCreate(**values)


def deduplicator_with(
    memory: MemoryRecord | None,
) -> MemoryDeduplicator:
    """Return a deduplicator with optional stored memory."""

    store = InMemoryMemoryStore()

    if memory is not None:
        store.add(memory)

    return MemoryDeduplicator(store=store)


def test_new_content_creates_memory() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(
            content="The project uses 256 dimensions."
        ),
        now=NOW,
    )

    assert result.action is (
        MemoryDeduplicationAction.CREATE
    )


def test_same_content_ignores_case_and_whitespace() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(
            content=(
                "  THE USER  prefers\n"
                "verified commands. "
            )
        ),
        now=NOW,
    )

    assert result.action is (
        MemoryDeduplicationAction.KEEP_EXISTING
    )


def test_different_subject_is_not_duplicate() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(subject_id="user-002"),
        now=NOW,
    )

    assert result.action is (
        MemoryDeduplicationAction.CREATE
    )


def test_higher_importance_updates_existing() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(importance=0.9),
        now=NOW,
    )

    assert result.action is (
        MemoryDeduplicationAction.UPDATE_EXISTING
    )
    assert (
        MemoryDeduplicationReason.IMPORTANCE_INCREASED
        in result.reasons
    )


def test_higher_confidence_updates_existing() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(confidence=1.0),
        now=NOW,
    )

    assert (
        MemoryDeduplicationReason.CONFIDENCE_INCREASED
        in result.reasons
    )


def test_new_tags_update_existing() -> None:
    result = deduplicator_with(
        stored_memory()
    ).evaluate(
        request=request(
            tags=["preference", "workflow"]
        ),
        now=NOW,
    )

    assert MemoryDeduplicationReason.TAGS_EXPANDED in (
        result.reasons
    )


def test_extended_expiration_updates_existing() -> None:
    existing = stored_memory(
        expires_at=NOW + timedelta(days=1)
    )
    result = deduplicator_with(existing).evaluate(
        request=request(
            expires_at=NOW + timedelta(days=2)
        ),
        now=NOW,
    )

    assert (
        MemoryDeduplicationReason.EXPIRATION_EXTENDED
        in result.reasons
    )


def test_expired_memory_is_not_duplicate() -> None:
    existing = stored_memory(
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=2),
        expires_at=NOW - timedelta(days=1),
    )
    result = deduplicator_with(existing).evaluate(
        request=request(),
        now=NOW,
    )

    assert result.action is (
        MemoryDeduplicationAction.CREATE
    )
