"""Tests for the in-memory research-agent message bus."""

from datetime import UTC, datetime, timedelta
from itertools import count

import pytest

from app.research.in_memory_research_agent_message_bus import (
    InMemoryResearchAgentMessageBus,
)
from app.research.research_agent_message_bus import (
    ResearchAgentDeliveryStatus,
)
from app.research.research_agent_message_bus_error import (
    ResearchAgentDeliveryAccessError,
    ResearchAgentDeliveryNotFoundError,
    ResearchAgentDeliveryStateError,
    ResearchAgentMessageAlreadyExistsError,
    ResearchAgentMessageNotFoundError,
)
from app.research.research_agent_registry import (
    ResearchAgentRegistry,
)
from app.research.research_agent_registry_error import (
    ResearchAgentRegistryError,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
    ResearchAgentMessagePriority,
    ResearchAgentMessageStatus,
    ResearchAgentMessageType,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
) -> ResearchAgentIdentity:
    """Return one valid agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager() -> ResearchAgentIdentity:
    """Return the manager agent."""

    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def search_agent() -> ResearchAgentIdentity:
    """Return the search specialist."""

    return identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def reader_agent() -> ResearchAgentIdentity:
    """Return the source reader."""

    return identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )


def registry() -> ResearchAgentRegistry:
    """Return a registry containing three agents."""

    return ResearchAgentRegistry(
        agents=[
            manager(),
            search_agent(),
            reader_agent(),
        ]
    )


def clock() -> callable:
    """Return a deterministic advancing clock."""

    current = datetime(
        2026,
        8,
        4,
        5,
        0,
        tzinfo=UTC,
    )
    ticks = count()

    def now() -> datetime:
        return current + timedelta(
            seconds=next(ticks)
        )

    return now


def delivery_ids() -> callable:
    """Return a deterministic delivery ID factory."""

    values = count(1)

    def create() -> str:
        return f"delivery-{next(values):03d}"

    return create


def bus() -> InMemoryResearchAgentMessageBus:
    """Return one deterministic in-memory bus."""

    return InMemoryResearchAgentMessageBus(
        registry=registry(),
        now=clock(),
        delivery_id_factory=delivery_ids(),
    )


def message(
    *,
    message_id: str = "message-001",
    recipient: ResearchAgentIdentity | None = None,
    broadcast: bool = False,
    priority: ResearchAgentMessagePriority = (
        ResearchAgentMessagePriority.NORMAL
    ),
    correlation_id: str = "correlation-001",
    sender: ResearchAgentIdentity | None = None,
) -> ResearchAgentMessage:
    """Return one valid message."""

    resolved_recipient = recipient

    if not broadcast and resolved_recipient is None:
        resolved_recipient = search_agent()

    return ResearchAgentMessage(
        message_id=message_id,
        message_type=(
            ResearchAgentMessageType.TASK_REQUEST
            if not broadcast
            else ResearchAgentMessageType.STATUS_UPDATE
        ),
        sender=sender or manager(),
        recipient=resolved_recipient,
        broadcast=broadcast,
        correlation_id=correlation_id,
        request_id="research-001",
        workspace_id="workspace-001",
        subject=f"Message {message_id}",
        payload={
            "task_id": "task-001",
        },
        priority=priority,
        status=ResearchAgentMessageStatus.CREATED,
        created_at=datetime(
            2026,
            8,
            4,
            5,
            0,
            tzinfo=UTC,
        ),
    )


def test_publish_creates_direct_delivery() -> None:
    message_bus = bus()

    deliveries = message_bus.publish(message())

    assert len(deliveries) == 1
    assert deliveries[0].delivery_id == "delivery-001"
    assert deliveries[0].recipient_agent_id == (
        "agent-search-001"
    )
    assert deliveries[0].status is (
        ResearchAgentDeliveryStatus.PENDING
    )
    assert message_bus.pending_count(
        "agent-search-001"
    ) == 1


def test_publish_creates_broadcast_deliveries() -> None:
    message_bus = bus()

    deliveries = message_bus.publish(
        message(
            recipient=None,
            broadcast=True,
        )
    )

    assert [
        delivery.recipient_agent_id
        for delivery in deliveries
    ] == [
        "agent-search-001",
        "agent-reader-001",
    ]
    assert message_bus.pending_count(
        "agent-manager-001"
    ) == 0


def test_publish_rejects_duplicate_message_id() -> None:
    message_bus = bus()
    message_bus.publish(message())

    with pytest.raises(
        ResearchAgentMessageAlreadyExistsError,
        match=(
            "message ID has already been published"
        ),
    ):
        message_bus.publish(
            message(
                message_id=" MESSAGE-001 "
            )
        )


def test_publish_requires_registered_sender() -> None:
    outsider = identity(
        agent_id="agent-outsider-001",
        role=ResearchAgentRole.MANAGER,
        name="Outsider",
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match="agent is not registered",
    ):
        bus().publish(
            message(sender=outsider)
        )


def test_publish_requires_registered_recipient() -> None:
    outsider = identity(
        agent_id="agent-outsider-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Outsider",
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match="agent is not registered",
    ):
        bus().publish(
            message(recipient=outsider)
        )


def test_receive_delivers_pending_message() -> None:
    message_bus = bus()
    message_bus.publish(message())

    received = message_bus.receive(
        "agent-search-001"
    )

    assert len(received) == 1
    assert received[0].message.message_id == "message-001"
    assert received[0].delivery.status is (
        ResearchAgentDeliveryStatus.DELIVERED
    )
    assert received[0].delivery.attempt_count == 1
    assert received[0].delivery.delivered_at is not None
    assert message_bus.pending_count(
        "agent-search-001"
    ) == 0


def test_receive_respects_limit() -> None:
    message_bus = bus()
    message_bus.publish(
        message(message_id="message-001")
    )
    message_bus.publish(
        message(message_id="message-002")
    )

    received = message_bus.receive(
        "agent-search-001",
        limit=1,
    )

    assert len(received) == 1
    assert message_bus.pending_count(
        "agent-search-001"
    ) == 1


def test_receive_prioritizes_high_priority() -> None:
    message_bus = bus()
    message_bus.publish(
        message(
            message_id="message-low",
            priority=ResearchAgentMessagePriority.LOW,
        )
    )
    message_bus.publish(
        message(
            message_id="message-critical",
            priority=(
                ResearchAgentMessagePriority.CRITICAL
            ),
        )
    )

    received = message_bus.receive(
        "agent-search-001",
        limit=2,
    )

    assert [
        item.message.message_id
        for item in received
    ] == [
        "message-critical",
        "message-low",
    ]


def test_receive_preserves_publish_order_at_same_priority() -> None:
    message_bus = bus()
    message_bus.publish(
        message(message_id="message-001")
    )
    message_bus.publish(
        message(message_id="message-002")
    )

    received = message_bus.receive(
        "agent-search-001",
        limit=2,
    )

    assert [
        item.message.message_id
        for item in received
    ] == [
        "message-001",
        "message-002",
    ]


def test_receive_rejects_invalid_limit() -> None:
    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        bus().receive(
            "agent-search-001",
            limit=0,
        )


def test_processing_and_acknowledgement_flow() -> None:
    message_bus = bus()
    message_bus.publish(message())

    received = message_bus.receive(
        "agent-search-001"
    )[0]

    processing = message_bus.start_processing(
        received.delivery.delivery_id,
        agent_id="agent-search-001",
    )
    acknowledged = message_bus.acknowledge(
        processing.delivery_id,
        agent_id="agent-search-001",
    )

    assert processing.status is (
        ResearchAgentDeliveryStatus.PROCESSING
    )
    assert acknowledged.status is (
        ResearchAgentDeliveryStatus.ACKNOWLEDGED
    )
    assert acknowledged.completed_at is not None
    assert acknowledged.is_terminal is True


def test_processing_failure_flow() -> None:
    message_bus = bus()
    message_bus.publish(message())

    received = message_bus.receive(
        "agent-search-001"
    )[0]

    processing = message_bus.start_processing(
        received.delivery.delivery_id,
        agent_id="agent-search-001",
    )
    failed = message_bus.fail(
        processing.delivery_id,
        agent_id="agent-search-001",
        reason="Search provider failed.",
    )

    assert failed.status is (
        ResearchAgentDeliveryStatus.FAILED
    )
    assert failed.failure_reason == (
        "Search provider failed."
    )
    assert failed.completed_at is not None


def test_delivery_access_is_restricted_to_recipient() -> None:
    message_bus = bus()
    message_bus.publish(message())

    received = message_bus.receive(
        "agent-search-001"
    )[0]

    with pytest.raises(
        ResearchAgentDeliveryAccessError,
        match="agent cannot access this delivery",
    ):
        message_bus.start_processing(
            received.delivery.delivery_id,
            agent_id="agent-reader-001",
        )


def test_start_processing_requires_delivered_state() -> None:
    message_bus = bus()
    delivery = message_bus.publish(message())[0]

    with pytest.raises(
        ResearchAgentDeliveryStateError,
        match=(
            "only delivered message can start processing"
        ),
    ):
        message_bus.start_processing(
            delivery.delivery_id,
            agent_id="agent-search-001",
        )


def test_acknowledge_requires_processing_state() -> None:
    message_bus = bus()
    message_bus.publish(message())

    received = message_bus.receive(
        "agent-search-001"
    )[0]

    with pytest.raises(
        ResearchAgentDeliveryStateError,
        match=(
            "only processing delivery can be acknowledged"
        ),
    ):
        message_bus.acknowledge(
            received.delivery.delivery_id,
            agent_id="agent-search-001",
        )


def test_fail_rejects_blank_reason() -> None:
    with pytest.raises(
        ValueError,
        match="reason must not be blank",
    ):
        bus().fail(
            "delivery-001",
            agent_id="agent-search-001",
            reason=" ",
        )


def test_cancel_nonterminal_delivery() -> None:
    message_bus = bus()
    delivery = message_bus.publish(message())[0]

    cancelled = message_bus.cancel(
        delivery.delivery_id
    )

    assert cancelled.status is (
        ResearchAgentDeliveryStatus.CANCELLED
    )
    assert cancelled.completed_at is not None


def test_cancel_rejects_terminal_delivery() -> None:
    message_bus = bus()
    delivery = message_bus.publish(message())[0]
    cancelled = message_bus.cancel(
        delivery.delivery_id
    )

    with pytest.raises(
        ResearchAgentDeliveryStateError,
        match=(
            "terminal delivery cannot be cancelled"
        ),
    ):
        message_bus.cancel(
            cancelled.delivery_id
        )


def test_message_and_delivery_lookup() -> None:
    message_bus = bus()
    created = message_bus.publish(message())[0]

    assert message_bus.message(
        " MESSAGE-001 "
    ) is not None
    assert message_bus.delivery(
        " DELIVERY-001 "
    ) == created
    assert message_bus.message("missing") is None
    assert message_bus.delivery("missing") is None


def test_deliveries_for_message() -> None:
    message_bus = bus()
    message_bus.publish(
        message(
            recipient=None,
            broadcast=True,
        )
    )

    deliveries = message_bus.deliveries_for_message(
        "message-001"
    )

    assert len(deliveries) == 2


def test_deliveries_for_missing_message_raises() -> None:
    with pytest.raises(
        ResearchAgentMessageNotFoundError,
        match="message was not found",
    ):
        bus().deliveries_for_message(
            "missing-message"
        )


def test_missing_delivery_raises() -> None:
    with pytest.raises(
        ResearchAgentDeliveryNotFoundError,
        match="delivery was not found",
    ):
        bus().cancel("missing-delivery")


def test_correlation_history_preserves_publish_order() -> None:
    message_bus = bus()
    message_bus.publish(
        message(
            message_id="message-001",
            correlation_id="correlation-shared",
        )
    )
    message_bus.publish(
        message(
            message_id="message-002",
            correlation_id="correlation-other",
        )
    )
    message_bus.publish(
        message(
            message_id="message-003",
            correlation_id=" CORRELATION-SHARED ",
        )
    )

    history = message_bus.correlation_history(
        "correlation-shared"
    )

    assert [
        item.message_id
        for item in history
    ] == [
        "message-001",
        "message-003",
    ]


@pytest.mark.parametrize(
    ("method_name", "value"),
    [
        ("message", " "),
        ("delivery", " "),
        ("deliveries_for_message", " "),
        ("pending_count", " "),
        ("correlation_history", " "),
    ],
)
def test_bus_rejects_blank_identifiers(
    method_name: str,
    value: str,
) -> None:
    message_bus = bus()
    method = getattr(message_bus, method_name)

    with pytest.raises(ValueError):
        method(value)
