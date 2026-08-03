"""Tests for the agent memory application service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.memory.clock import Clock
from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.memory_id_generator import (
    MemoryIdGenerator,
)
from app.memory.memory_service import (
    MemoryService,
    MemoryServiceError,
)
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
    MemorySource,
)
from app.schemas.memory_update import MemoryUpdate

INITIAL_TIME = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return a controllable UTC timestamp."""

    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class SequenceIdGenerator(MemoryIdGenerator):
    """Return predefined memory IDs."""

    def __init__(self, values: list[str]) -> None:
        self._values = list(values)

    def generate(self) -> str:
        return self._values.pop(0)


def request(
    **overrides: object,
) -> MemoryCreate:
    """Return one valid user semantic-memory request."""

    values: dict[str, object] = {
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "tags": ["preference"],
        "importance": 0.8,
        "confidence": 1.0,
    }
    values.update(overrides)

    return MemoryCreate(**values)


def make_service(
    *,
    clock: FixedClock | None = None,
    ids: list[str] | None = None,
) -> tuple[
    MemoryService,
    InMemoryMemoryStore,
    FixedClock,
]:
    """Create a deterministic memory service."""

    effective_clock = clock or FixedClock(INITIAL_TIME)
    store = InMemoryMemoryStore()
    service = MemoryService(
        store=store,
        clock=effective_clock,
        id_generator=SequenceIdGenerator(
            ids or ["mem-001", "mem-002"]
        ),
    )

    return service, store, effective_clock


def test_create_assigns_id_and_timestamps() -> None:
    service, store, _ = make_service()

    created = service.create(request())

    assert created.memory_id == "mem-001"
    assert created.created_at == INITIAL_TIME
    assert created.updated_at == INITIAL_TIME
    assert store.get("mem-001") == created


def test_create_preserves_supplied_values() -> None:
    service, _, _ = make_service()

    created = service.create(
        request(
            content="Project uses 256 embedding dimensions.",
            importance=0.9,
            metadata={"phase": "rag"},
        )
    )

    assert created.content == (
        "Project uses 256 embedding dimensions."
    )
    assert created.importance == 0.9
    assert created.metadata == {"phase": "rag"}


def test_create_rejects_blank_generated_id() -> None:
    service, _, _ = make_service(ids=["   "])

    with pytest.raises(
        MemoryServiceError,
        match="blank ID",
    ):
        service.create(request())


def test_create_rejects_expiration_not_after_now() -> None:
    service, _, _ = make_service()

    with pytest.raises(
        MemoryServiceError,
        match="later than creation time",
    ):
        service.create(
            request(expires_at=INITIAL_TIME)
        )


def test_get_without_access_record_does_not_modify_memory() -> None:
    service, _, clock = make_service()
    created = service.create(request())

    clock.value = INITIAL_TIME + timedelta(minutes=5)
    loaded = service.get(
        created.memory_id,
        record_access=False,
    )

    assert loaded.last_accessed_at is None
    assert loaded.updated_at == INITIAL_TIME


def test_get_can_record_access_time() -> None:
    service, _, clock = make_service()
    created = service.create(request())

    access_time = INITIAL_TIME + timedelta(minutes=5)
    clock.value = access_time

    loaded = service.get(
        created.memory_id,
        record_access=True,
    )

    assert loaded.last_accessed_at == access_time
    assert loaded.updated_at == access_time


def test_touch_records_access_time() -> None:
    service, _, clock = make_service()
    created = service.create(request())

    touch_time = INITIAL_TIME + timedelta(minutes=10)
    clock.value = touch_time

    touched = service.touch(created.memory_id)

    assert touched.last_accessed_at == touch_time
    assert touched.updated_at == touch_time


def test_update_assigns_current_updated_at() -> None:
    service, _, clock = make_service()
    created = service.create(request())

    update_time = INITIAL_TIME + timedelta(hours=1)
    clock.value = update_time

    updated = service.update(
        memory_id=created.memory_id,
        update=MemoryUpdate(
            content="Updated preference.",
            importance=1.0,
        ),
    )

    assert updated.content == "Updated preference."
    assert updated.importance == 1.0
    assert updated.updated_at == update_time
    assert updated.created_at == INITIAL_TIME


def test_update_rejects_invalid_expiration() -> None:
    service, _, clock = make_service()
    created = service.create(request())

    clock.value = INITIAL_TIME + timedelta(minutes=1)

    with pytest.raises(
        MemoryServiceError,
        match="later than creation time",
    ):
        service.update(
            memory_id=created.memory_id,
            update=MemoryUpdate(
                expires_at=INITIAL_TIME,
            ),
        )


def test_list_excludes_expired_memory_using_clock() -> None:
    service, _, clock = make_service()

    service.create(
        request(
            expires_at=INITIAL_TIME + timedelta(hours=1)
        )
    )

    assert service.count() == 1

    clock.value = INITIAL_TIME + timedelta(hours=1)

    assert service.list() == []
    assert service.count() == 0


def test_list_applies_query_filters() -> None:
    service, _, _ = make_service()

    service.create(
        request(
            importance=0.9,
            tags=["preference", "workflow"],
        )
    )
    service.create(
        request(
            importance=0.4,
            tags=["temporary"],
        )
    )

    results = service.list(
        query=MemoryQuery(
            tags=["workflow"],
            minimum_importance=0.8,
        )
    )

    assert [
        memory.memory_id
        for memory in results
    ] == ["mem-001"]


def test_delete_removes_memory() -> None:
    service, _, _ = make_service()
    created = service.create(request())

    deleted = service.delete(created.memory_id)

    assert deleted.memory_id == created.memory_id
    assert service.count() == 0


def test_clear_removes_all_memories() -> None:
    service, _, _ = make_service()

    service.create(request())
    service.create(request())

    service.clear()

    assert service.count() == 0


def test_service_rejects_naive_clock() -> None:
    clock = FixedClock(
        INITIAL_TIME.replace(tzinfo=None)
    )
    service, _, _ = make_service(clock=clock)

    with pytest.raises(
        MemoryServiceError,
        match="timezone-aware",
    ):
        service.create(request())


def test_service_rejects_non_utc_clock() -> None:
    non_utc = INITIAL_TIME.astimezone(
        timezone(timedelta(hours=9))
    )
    clock = FixedClock(non_utc)
    service, _, _ = make_service(clock=clock)

    with pytest.raises(
        MemoryServiceError,
        match="must return UTC",
    ):
        service.create(request())
