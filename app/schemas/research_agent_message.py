"""Schemas for structured communication between research agents."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.schemas.research_agent import ResearchAgentIdentity


class ResearchAgentMessageType(StrEnum):
    """Supported semantic message types."""

    TASK_REQUEST = "task_request"
    TASK_ACCEPTED = "task_accepted"
    TASK_REJECTED = "task_rejected"
    TASK_RESULT = "task_result"
    REVIEW_REQUEST = "review_request"
    REVIEW_RESULT = "review_result"
    REVISION_REQUEST = "revision_request"
    REVISION_RESULT = "revision_result"
    INFORMATION_REQUEST = "information_request"
    INFORMATION_RESPONSE = "information_response"
    STATUS_UPDATE = "status_update"
    FAILURE = "failure"
    CANCELLATION = "cancellation"


class ResearchAgentMessageStatus(StrEnum):
    """Delivery and processing status of one message."""

    CREATED = "created"
    QUEUED = "queued"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchAgentMessagePriority(IntEnum):
    """Priority used when ordering agent messages."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    CRITICAL = 40


class ResearchAgentMessageError(BaseModel):
    """Structured error attached to a failure message."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    code: str
    message: str
    retryable: bool = False
    details: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        """Validate structured message error fields."""

        if not self.code.strip():
            raise ValueError(
                "error code must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "error message must not be blank"
            )

        if any(
            not key.strip()
            for key in self.details
        ):
            raise ValueError(
                "error detail keys must not be blank"
            )

        return self


class ResearchAgentMessage(BaseModel):
    """Immutable structured message exchanged by research agents."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    message_id: str
    message_type: ResearchAgentMessageType
    sender: ResearchAgentIdentity
    recipient: ResearchAgentIdentity | None = None
    broadcast: bool = False
    correlation_id: str
    causation_id: str | None = None
    reply_to_message_id: str | None = None
    assignment_id: str | None = None
    request_id: str
    workspace_id: str
    subject: str
    payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    priority: ResearchAgentMessagePriority = (
        ResearchAgentMessagePriority.NORMAL
    )
    status: ResearchAgentMessageStatus = (
        ResearchAgentMessageStatus.CREATED
    )
    error: ResearchAgentMessageError | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_message(self) -> Self:
        """Validate identity, routing, and message semantics."""

        required_text = {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "subject": self.subject,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_optional_identifier(
            self.causation_id,
            field_name="causation_id",
        )
        self._validate_optional_identifier(
            self.reply_to_message_id,
            field_name="reply_to_message_id",
        )
        self._validate_optional_identifier(
            self.assignment_id,
            field_name="assignment_id",
        )

        self._validate_routing()
        self._validate_error_semantics()
        self._validate_payload()
        self._validate_metadata()

        return self

    @staticmethod
    def _validate_optional_identifier(
        value: str | None,
        *,
        field_name: str,
    ) -> None:
        """Validate an optional identifier."""

        if value is not None and not value.strip():
            raise ValueError(
                f"{field_name} must not be blank when provided"
            )

    def _validate_routing(self) -> None:
        """Validate direct and broadcast routing."""

        if self.broadcast and self.recipient is not None:
            raise ValueError(
                "broadcast message must not define recipient"
            )

        if not self.broadcast and self.recipient is None:
            raise ValueError(
                "direct message must define recipient"
            )

        if (
            self.recipient is not None
            and self.sender.agent_id.strip().casefold()
            == self.recipient.agent_id.strip().casefold()
        ):
            raise ValueError(
                "sender and recipient must be different agents"
            )

    def _validate_error_semantics(self) -> None:
        """Validate error requirements for failed messages."""

        requires_error = (
            self.message_type
            is ResearchAgentMessageType.FAILURE
            or self.status
            is ResearchAgentMessageStatus.FAILED
        )

        if requires_error and self.error is None:
            raise ValueError(
                "failed message must include error"
            )

        if not requires_error and self.error is not None:
            raise ValueError(
                "non-failed message must not include error"
            )

    def _validate_payload(self) -> None:
        """Validate payload keys."""

        if any(
            not key.strip()
            for key in self.payload
        ):
            raise ValueError(
                "payload keys must not be blank"
            )

    def _validate_metadata(self) -> None:
        """Validate message metadata."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def is_reply(self) -> bool:
        """Return whether the message replies to another message."""

        return self.reply_to_message_id is not None

    @property
    def is_terminal(self) -> bool:
        """Return whether message processing has reached a terminal state."""

        return self.status in {
            ResearchAgentMessageStatus.COMPLETED,
            ResearchAgentMessageStatus.FAILED,
            ResearchAgentMessageStatus.CANCELLED,
        }

    def is_addressed_to(
        self,
        agent: ResearchAgentIdentity,
    ) -> bool:
        """Return whether a message is visible to an agent."""

        if self.broadcast:
            return (
                agent.agent_id.strip().casefold()
                != self.sender.agent_id.strip().casefold()
            )

        if self.recipient is None:
            return False

        return (
            self.recipient.agent_id.strip().casefold()
            == agent.agent_id.strip().casefold()
        )
