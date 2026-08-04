"""Tests for structured research-agent messages."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
    ResearchAgentMessageError,
    ResearchAgentMessagePriority,
    ResearchAgentMessageStatus,
    ResearchAgentMessageType,
)


def agent(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
) -> ResearchAgentIdentity:
    """Return one valid research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def sender() -> ResearchAgentIdentity:
    """Return the manager agent."""

    return agent(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def recipient() -> ResearchAgentIdentity:
    """Return the search specialist agent."""

    return agent(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def message(
    **overrides: object,
) -> ResearchAgentMessage:
    """Return one valid direct agent message."""

    values: dict[str, object] = {
        "message_id": "message-001",
        "message_type": (
            ResearchAgentMessageType.TASK_REQUEST
        ),
        "sender": sender(),
        "recipient": recipient(),
        "broadcast": False,
        "correlation_id": "correlation-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "subject": "Search for agent-memory sources",
        "payload": {
            "task_id": "task-001",
            "maximum_sources": 5,
        },
        "priority": (
            ResearchAgentMessagePriority.NORMAL
        ),
        "status": ResearchAgentMessageStatus.CREATED,
        "created_at": datetime(
            2026,
            8,
            4,
            4,
            0,
            tzinfo=UTC,
        ),
        "metadata": {
            "origin": "manager",
        },
    }
    values.update(overrides)

    return ResearchAgentMessage.model_validate(
        values
    )


def failure_error() -> ResearchAgentMessageError:
    """Return one valid message error."""

    return ResearchAgentMessageError(
        code="SEARCH_FAILED",
        message="No source provider was available.",
        retryable=True,
        details={
            "provider_count": 0,
        },
    )


def test_message_accepts_valid_direct_message() -> None:
    value = message()

    assert value.sender.agent_id == "agent-manager-001"
    assert value.recipient is not None
    assert value.recipient.agent_id == "agent-search-001"
    assert value.is_reply is False
    assert value.is_terminal is False


@pytest.mark.parametrize(
    "field_name",
    [
        "message_id",
        "correlation_id",
        "request_id",
        "workspace_id",
        "subject",
    ],
)
def test_message_rejects_blank_required_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        message(**{field_name: " "})


def test_message_rejects_direct_message_without_recipient() -> None:
    with pytest.raises(
        ValidationError,
        match="direct message must define recipient",
    ):
        message(recipient=None)


def test_message_accepts_broadcast_without_recipient() -> None:
    value = message(
        recipient=None,
        broadcast=True,
        message_type=(
            ResearchAgentMessageType.STATUS_UPDATE
        ),
    )

    assert value.broadcast is True
    assert value.recipient is None


def test_message_rejects_broadcast_with_recipient() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "broadcast message must not define recipient"
        ),
    ):
        message(broadcast=True)


def test_message_rejects_same_sender_and_recipient() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "sender and recipient must be different agents"
        ),
    ):
        message(recipient=sender())


def test_failure_message_requires_error() -> None:
    with pytest.raises(
        ValidationError,
        match="failed message must include error",
    ):
        message(
            message_type=ResearchAgentMessageType.FAILURE,
            status=ResearchAgentMessageStatus.FAILED,
        )


def test_failure_message_accepts_error() -> None:
    value = message(
        message_type=ResearchAgentMessageType.FAILURE,
        status=ResearchAgentMessageStatus.FAILED,
        error=failure_error(),
    )

    assert value.error is not None
    assert value.error.retryable is True
    assert value.is_terminal is True


def test_non_failed_message_rejects_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "non-failed message must not include error"
        ),
    ):
        message(error=failure_error())


def test_message_accepts_reply_reference() -> None:
    value = message(
        message_type=(
            ResearchAgentMessageType.TASK_ACCEPTED
        ),
        sender=recipient(),
        recipient=sender(),
        message_id="message-002",
        causation_id="message-001",
        reply_to_message_id="message-001",
    )

    assert value.is_reply is True
    assert value.reply_to_message_id == "message-001"


def test_message_rejects_blank_optional_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "reply_to_message_id must not be blank "
            "when provided"
        ),
    ):
        message(reply_to_message_id=" ")


def test_message_rejects_blank_payload_key() -> None:
    with pytest.raises(
        ValidationError,
        match="payload keys must not be blank",
    ):
        message(
            payload={
                " ": "value",
            }
        )


def test_message_checks_direct_recipient() -> None:
    value = message()

    assert value.is_addressed_to(recipient())
    assert not value.is_addressed_to(sender())


def test_broadcast_is_visible_to_other_agents() -> None:
    value = message(
        recipient=None,
        broadcast=True,
        message_type=(
            ResearchAgentMessageType.STATUS_UPDATE
        ),
    )

    assert value.is_addressed_to(recipient())
    assert not value.is_addressed_to(sender())


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentMessageStatus.COMPLETED,
        ResearchAgentMessageStatus.CANCELLED,
    ],
)
def test_message_reports_terminal_status(
    status: ResearchAgentMessageStatus,
) -> None:
    value = message(status=status)

    assert value.is_terminal is True


def test_error_rejects_blank_code() -> None:
    with pytest.raises(
        ValidationError,
        match="error code must not be blank",
    ):
        ResearchAgentMessageError(
            code=" ",
            message="Failure.",
        )


def test_error_rejects_blank_detail_key() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "error detail keys must not be blank"
        ),
    ):
        ResearchAgentMessageError(
            code="FAILED",
            message="Failure.",
            details={
                " ": "value",
            },
        )


def test_message_is_frozen() -> None:
    value = message()

    with pytest.raises(ValidationError):
        value.subject = "Changed"
