"""Tests for the research-agent message bus contract."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.research.research_agent_message_bus import (
    ResearchAgentDeliveryStatus,
    ResearchAgentMessageBus,
    ResearchAgentMessageDelivery,
    ResearchAgentReceivedMessage,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
    ResearchAgentMessageStatus,
    ResearchAgentMessageType,
)


def agent(
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
    """Return one manager agent."""

    return agent(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def search_agent() -> ResearchAgentIdentity:
    """Return one search specialist."""

    return agent(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def message(
    **overrides: object,
) -> ResearchAgentMessage:
    """Return one valid direct message."""

    values: dict[str, object] = {
        "message_id": "message-001",
        "message_type": (
            ResearchAgentMessageType.TASK_REQUEST
        ),
        "sender": manager(),
        "recipient": search_agent(),
        "broadcast": False,
        "correlation_id": "correlation-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "subject": "Search sources",
        "payload": {
            "task_id": "task-001",
        },
        "status": ResearchAgentMessageStatus.CREATED,
        "created_at": datetime(
            2026,
            8,
            4,
            5,
            0,
            tzinfo=UTC,
        ),
    }
    values.update(overrides)

    return ResearchAgentMessage.model_validate(
        values
    )


def delivery(
    **overrides: object,
) -> ResearchAgentMessageDelivery:
    """Return one valid pending delivery."""

    values: dict[str, object] = {
        "delivery_id": "delivery-001",
        "message_id": "message-001",
        "recipient_agent_id": "agent-search-001",
        "status": ResearchAgentDeliveryStatus.PENDING,
        "attempt_count": 0,
        "created_at": datetime(
            2026,
            8,
            4,
            5,
            0,
            tzinfo=UTC,
        ),
        "metadata": {
            "transport": "in-memory",
        },
    }
    values.update(overrides)

    return ResearchAgentMessageDelivery.model_validate(
        values
    )


def test_message_bus_is_abstract() -> None:
    with pytest.raises(TypeError):
        ResearchAgentMessageBus()


def test_delivery_accepts_pending_state() -> None:
    value = delivery()

    assert value.status is (
        ResearchAgentDeliveryStatus.PENDING
    )
    assert value.is_terminal is False


@pytest.mark.parametrize(
    "field_name",
    [
        "delivery_id",
        "message_id",
        "recipient_agent_id",
    ],
)
def test_delivery_rejects_blank_required_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        delivery(**{field_name: " "})


def test_failed_delivery_requires_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed delivery must include failure_reason"
        ),
    ):
        delivery(
            status=ResearchAgentDeliveryStatus.FAILED,
            completed_at=datetime(
                2026,
                8,
                4,
                5,
                2,
                tzinfo=UTC,
            ),
        )


def test_non_failed_delivery_rejects_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "non-failed delivery must not include "
            "failure_reason"
        ),
    ):
        delivery(
            failure_reason="Unexpected failure."
        )


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentDeliveryStatus.DELIVERED,
        ResearchAgentDeliveryStatus.PROCESSING,
        ResearchAgentDeliveryStatus.ACKNOWLEDGED,
    ],
)
def test_delivered_states_require_delivered_at(
    status: ResearchAgentDeliveryStatus,
) -> None:
    values: dict[str, object] = {
        "status": status,
    }

    if status is ResearchAgentDeliveryStatus.ACKNOWLEDGED:
        values["completed_at"] = datetime(
            2026,
            8,
            4,
            5,
            2,
            tzinfo=UTC,
        )

    with pytest.raises(
        ValidationError,
        match=(
            "delivered delivery state must include "
            "delivered_at"
        ),
    ):
        delivery(**values)


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentDeliveryStatus.ACKNOWLEDGED,
        ResearchAgentDeliveryStatus.FAILED,
        ResearchAgentDeliveryStatus.CANCELLED,
    ],
)
def test_terminal_states_require_completed_at(
    status: ResearchAgentDeliveryStatus,
) -> None:
    values: dict[str, object] = {
        "status": status,
    }

    if status is ResearchAgentDeliveryStatus.ACKNOWLEDGED:
        values["delivered_at"] = datetime(
            2026,
            8,
            4,
            5,
            1,
            tzinfo=UTC,
        )

    if status is ResearchAgentDeliveryStatus.FAILED:
        values["failure_reason"] = "Processing failed."

    with pytest.raises(
        ValidationError,
        match=(
            "terminal delivery state must include "
            "completed_at"
        ),
    ):
        delivery(**values)


def test_acknowledged_delivery_is_terminal() -> None:
    value = delivery(
        status=ResearchAgentDeliveryStatus.ACKNOWLEDGED,
        attempt_count=1,
        delivered_at=datetime(
            2026,
            8,
            4,
            5,
            1,
            tzinfo=UTC,
        ),
        completed_at=datetime(
            2026,
            8,
            4,
            5,
            2,
            tzinfo=UTC,
        ),
    )

    assert value.is_terminal is True


def test_delivery_rejects_invalid_timestamp_order() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "delivered_at must not precede created_at"
        ),
    ):
        delivery(
            status=ResearchAgentDeliveryStatus.DELIVERED,
            delivered_at=datetime(
                2026,
                8,
                4,
                4,
                59,
                tzinfo=UTC,
            ),
        )


def test_received_message_accepts_matching_delivery() -> None:
    value = ResearchAgentReceivedMessage(
        message=message(),
        delivery=delivery(),
    )

    assert value.message.message_id == "message-001"
    assert value.delivery.delivery_id == "delivery-001"


def test_received_message_rejects_message_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "delivery message_id must match message"
        ),
    ):
        ResearchAgentReceivedMessage(
            message=message(),
            delivery=delivery(
                message_id="message-002"
            ),
        )


def test_received_message_rejects_recipient_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "delivery recipient must match "
            "message recipient"
        ),
    ):
        ResearchAgentReceivedMessage(
            message=message(),
            delivery=delivery(
                recipient_agent_id="agent-reader-001"
            ),
        )


def test_broadcast_received_message_accepts_delivery_recipient() -> None:
    broadcast = message(
        recipient=None,
        broadcast=True,
        message_type=(
            ResearchAgentMessageType.STATUS_UPDATE
        ),
    )

    value = ResearchAgentReceivedMessage(
        message=broadcast,
        delivery=delivery(),
    )

    assert value.message.broadcast is True


def test_delivery_is_frozen() -> None:
    value = delivery()

    with pytest.raises(ValidationError):
        value.attempt_count = 1
