"""Tests for the in-memory agent memory store."""

from datetime import UTC, datetime, timedelta

import pytest

from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.memory_store import (
    DuplicateMemoryError,
    MemoryNotFoundError,
)
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_update import MemoryUpdate

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
    memory_id: str,
    kind: MemoryKind = MemoryKind.SEMANTIC,
    scope: MemoryScope = MemoryScope.USER,
    subject_id: str | None = "user-001",
    project_id: str | None = None,
    session_id: str | None = None,
    content: str = "Stored memory.",
    tags: list[str] | None = None,
    importance: float = 0.5,
    confidence: float = 1.0,
    created_at: datetime = NOW,
    expires_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
) -> MemoryRecord:
    """Create one valid memory record."""

    return MemoryRecord(
        memory_id=memory_id,
        kind=kind,
        scope=scope,
        source=MemorySource.USER_STATEMENT,
        content=content,
        subject_id=subject_id,
        project_id=project_id,
        session_id=session_id,
        tags=tags or [],
        importance=importance,
        confidence=confidence,
        created_at=created_at,
        updated_at=created_at,
        expires_at=expires_at,
        metadata=metadata or {},
    )


def test_add_and_get_memory() -> None:
    store = InMemoryMemoryStore()
    original = memory(memory_id="mem-001")

    stored = store.add(original)
    loaded = store.get("mem-001")

    assert stored == original
    assert loaded == original
    assert loaded is not original


def test_add_rejects_duplicate_memory_id() -> None:
    store = InMemoryMemoryStore()
    store.add(memory(memory_id="mem-001"))

    with pytest.raises(
        DuplicateMemoryError,
        match="memory already exists",
    ):
        store.add(memory(memory_id="mem-001"))


def test_get_rejects_missing_memory() -> None:
    store = InMemoryMemoryStore()

    with pytest.raises(
        MemoryNotFoundError,
        match="memory not found",
    ):
        store.get("missing")


def test_list_returns_deterministic_order() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="mem-b",
            created_at=NOW,
        )
    )
    store.add(
        memory(
            memory_id="mem-a",
            created_at=NOW,
        )
    )
    store.add(
        memory(
            memory_id="mem-old",
            created_at=NOW - timedelta(days=1),
        )
    )

    assert [
        item.memory_id
        for item in store.list(now=NOW)
    ] == [
        "mem-old",
        "mem-a",
        "mem-b",
    ]


def test_list_excludes_expired_memories_by_default() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="active",
            expires_at=NOW + timedelta(hours=1),
        )
    )
    store.add(
        memory(
            memory_id="expired",
            created_at=NOW - timedelta(days=1),
            expires_at=NOW,
        )
    )

    assert [
        item.memory_id
        for item in store.list(now=NOW)
    ] == ["active"]


def test_list_can_include_expired_memories() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="expired",
            created_at=NOW - timedelta(days=1),
            expires_at=NOW,
        )
    )

    results = store.list(
        query=MemoryQuery(include_expired=True),
        now=NOW,
    )

    assert [
        item.memory_id
        for item in results
    ] == ["expired"]


def test_list_filters_by_kind_scope_and_subject() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="user-semantic",
            kind=MemoryKind.SEMANTIC,
        )
    )
    store.add(
        memory(
            memory_id="user-episodic",
            kind=MemoryKind.EPISODIC,
        )
    )
    store.add(
        memory(
            memory_id="other-user",
            subject_id="user-002",
        )
    )

    results = store.list(
        query=MemoryQuery(
            kinds=[MemoryKind.SEMANTIC],
            scopes=[MemoryScope.USER],
            subject_id="user-001",
        ),
        now=NOW,
    )

    assert [
        item.memory_id
        for item in results
    ] == ["user-semantic"]


def test_list_requires_all_query_tags() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="matching",
            tags=["preference", "workflow"],
        )
    )
    store.add(
        memory(
            memory_id="partial",
            tags=["preference"],
        )
    )

    results = store.list(
        query=MemoryQuery(
            tags=["Preference", "WORKFLOW"]
        ),
        now=NOW,
    )

    assert [
        item.memory_id
        for item in results
    ] == ["matching"]


def test_list_filters_importance_and_confidence() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="strong",
            importance=0.9,
            confidence=0.95,
        )
    )
    store.add(
        memory(
            memory_id="weak",
            importance=0.4,
            confidence=0.7,
        )
    )

    results = store.list(
        query=MemoryQuery(
            minimum_importance=0.8,
            minimum_confidence=0.9,
        ),
        now=NOW,
    )

    assert [
        item.memory_id
        for item in results
    ] == ["strong"]


def test_update_changes_mutable_fields() -> None:
    store = InMemoryMemoryStore()
    store.add(memory(memory_id="mem-001"))

    updated = store.update(
        memory_id="mem-001",
        update=MemoryUpdate(
            content="Updated content.",
            tags=["updated"],
            importance=0.9,
            metadata={"reason": "user correction"},
        ),
        updated_at=NOW + timedelta(minutes=5),
    )

    assert updated.content == "Updated content."
    assert updated.tags == ["updated"]
    assert updated.importance == 0.9
    assert updated.metadata == {
        "reason": "user correction"
    }
    assert updated.updated_at == (
        NOW + timedelta(minutes=5)
    )


def test_update_revalidates_expiration() -> None:
    store = InMemoryMemoryStore()
    store.add(memory(memory_id="mem-001"))

    with pytest.raises(
        ValueError,
        match="expires_at must be later than created_at",
    ):
        store.update(
            memory_id="mem-001",
            update=MemoryUpdate(
                expires_at=NOW,
            ),
            updated_at=NOW + timedelta(minutes=1),
        )


def test_update_rejects_missing_memory() -> None:
    store = InMemoryMemoryStore()

    with pytest.raises(MemoryNotFoundError):
        store.update(
            memory_id="missing",
            update=MemoryUpdate(content="Updated."),
            updated_at=NOW,
        )


def test_delete_returns_removed_memory() -> None:
    store = InMemoryMemoryStore()
    store.add(memory(memory_id="mem-001"))

    deleted = store.delete("mem-001")

    assert deleted.memory_id == "mem-001"
    assert store.count(now=NOW) == 0


def test_delete_rejects_missing_memory() -> None:
    store = InMemoryMemoryStore()

    with pytest.raises(MemoryNotFoundError):
        store.delete("missing")


def test_clear_removes_all_memories() -> None:
    store = InMemoryMemoryStore()
    store.add(memory(memory_id="mem-001"))
    store.add(memory(memory_id="mem-002"))

    store.clear()

    assert store.count(now=NOW) == 0


def test_count_uses_query_filters() -> None:
    store = InMemoryMemoryStore()

    store.add(
        memory(
            memory_id="important",
            importance=0.9,
        )
    )
    store.add(
        memory(
            memory_id="ordinary",
            importance=0.5,
        )
    )

    assert store.count(
        query=MemoryQuery(
            minimum_importance=0.8
        ),
        now=NOW,
    ) == 1


def test_store_rejects_blank_memory_id() -> None:
    store = InMemoryMemoryStore()

    with pytest.raises(
        ValueError,
        match="memory ID must not be blank",
    ):
        store.get("   ")


def test_store_returns_defensive_copy() -> None:
    store = InMemoryMemoryStore()
    store.add(
        memory(
            memory_id="mem-001",
            metadata={"nested": {"value": 1}},
        )
    )

    loaded = store.get("mem-001")
    loaded.metadata["nested"]["value"] = 99

    reloaded = store.get("mem-001")

    assert reloaded.metadata == {
        "nested": {"value": 1}
    }
