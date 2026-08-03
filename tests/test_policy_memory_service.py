"""Tests for memory creation with policy enforcement."""

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.memory.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from app.memory.memory_id_generator import (
    MemoryIdGenerator,
)
from app.memory.memory_policy import MemoryPolicy
from app.memory.memory_service import MemoryService
from app.memory.policy_memory_service import (
    MemoryApprovalRequiredError,
    MemoryPolicyRejectedError,
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


class FixedIdGenerator(MemoryIdGenerator):
    """Return one fixed memory ID."""

    def generate(self) -> str:
        return "mem-policy-001"


def service() -> PolicyMemoryService:
    """Return a deterministic policy memory service."""

    memory_service = MemoryService(
        store=InMemoryMemoryStore(),
        clock=FixedClock(),
        id_generator=FixedIdGenerator(),
    )

    return PolicyMemoryService(
        memory_service=memory_service,
        policy=MemoryPolicy(),
    )


def user_request(
    **overrides: object,
) -> MemoryCreate:
    """Return one direct user memory request."""

    values: dict[str, object] = {
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "importance": 0.8,
        "confidence": 1.0,
    }
    values.update(overrides)

    return MemoryCreate(**values)


def test_creates_allowed_memory() -> None:
    policy_service = service()

    created = policy_service.create(user_request())

    assert created.memory_id == "mem-policy-001"
    assert policy_service.memory_service.count() == 1


def test_rejected_memory_is_not_stored() -> None:
    policy_service = service()

    with pytest.raises(MemoryPolicyRejectedError):
        policy_service.create(
            user_request(importance=0.1)
        )

    assert policy_service.memory_service.count() == 0


def test_inference_requires_approval() -> None:
    policy_service = service()
    request = user_request(
        source=MemorySource.AGENT_INFERENCE,
        source_reference="turn-123",
        confidence=0.9,
    )

    with pytest.raises(
        MemoryApprovalRequiredError
    ):
        policy_service.create(request)

    assert policy_service.memory_service.count() == 0


def test_approved_inference_is_stored() -> None:
    policy_service = service()
    request = user_request(
        source=MemorySource.AGENT_INFERENCE,
        source_reference="turn-123",
        confidence=0.9,
    )

    created = policy_service.create(
        request,
        user_approved=True,
    )

    assert created.source is (
        MemorySource.AGENT_INFERENCE
    )
    assert policy_service.memory_service.count() == 1


def test_evaluate_does_not_store_memory() -> None:
    policy_service = service()

    result = policy_service.evaluate(user_request())

    assert result.decision.value == "allow"
    assert policy_service.memory_service.count() == 0
