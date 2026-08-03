"""Tests for policy-aware duplicate memory handling."""

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.memory.deduplicating_memory_service import (
    DeduplicatingMemoryService,
)
from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.memory_deduplicator import (
    MemoryDeduplicator,
)
from app.memory.memory_id_generator import (
    MemoryIdGenerator,
)
from app.memory.memory_policy import MemoryPolicy
from app.memory.memory_service import MemoryService
from app.memory.policy_memory_service import (
    PolicyMemoryService,
)
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_record import (
    MemoryKind,
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


class FixedClock(Clock):
    """Return one fixed timestamp."""

    def now(self) -> datetime:
        return NOW


class SequenceIdGenerator(MemoryIdGenerator):
    """Return sequential predefined IDs."""

    def __init__(self) -> None:
        self._counter = 0

    def generate(self) -> str:
        self._counter += 1

        return f"mem-{self._counter:03d}"


def request(
    **overrides: object,
) -> MemoryCreate:
    """Return one valid candidate memory."""

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


def make_service() -> DeduplicatingMemoryService:
    """Return a deterministic service."""

    store = InMemoryMemoryStore()
    memory_service = MemoryService(
        store=store,
        clock=FixedClock(),
        id_generator=SequenceIdGenerator(),
    )
    policy_service = PolicyMemoryService(
        memory_service=memory_service,
        policy=MemoryPolicy(),
    )

    return DeduplicatingMemoryService(
        policy_service=policy_service,
        deduplicator=MemoryDeduplicator(
            store=store
        ),
    )


def test_new_memory_is_created() -> None:
    service = make_service()

    created = service.create(request())

    assert created.memory_id == "mem-001"
    assert service.memory_service.count() == 1


def test_exact_duplicate_returns_existing_record() -> None:
    service = make_service()

    first = service.create(request())
    second = service.create(
        request(
            content=(
                " THE USER prefers  verified commands. "
            )
        )
    )

    assert second.memory_id == first.memory_id
    assert service.memory_service.count() == 1


def test_improved_duplicate_updates_existing() -> None:
    service = make_service()

    first = service.create(request())
    updated = service.create(
        request(
            tags=["preference", "workflow"],
            importance=0.9,
            confidence=1.0,
            metadata={"confirmed": True},
        )
    )

    assert updated.memory_id == first.memory_id
    assert updated.importance == 0.9
    assert updated.confidence == 1.0
    assert updated.tags == [
        "preference",
        "workflow",
    ]
    assert updated.metadata == {
        "confirmed": True
    }
    assert service.memory_service.count() == 1


def test_different_content_creates_second_memory() -> None:
    service = make_service()

    first = service.create(request())
    second = service.create(
        request(
            content="The project uses 256 dimensions."
        )
    )

    assert first.memory_id == "mem-001"
    assert second.memory_id == "mem-002"
    assert service.memory_service.count() == 2


def test_policy_is_checked_before_deduplication() -> None:
    service = make_service()

    service.create(request())

    from app.memory.policy_memory_service import (
        MemoryPolicyRejectedError,
    )

    with pytest.raises(MemoryPolicyRejectedError):
        service.create(
            request(importance=0.1)
        )

    assert service.memory_service.count() == 1
