"""Contract for research-agent message bus implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_agent_message import (
    ResearchAgentMessage,
)


class ResearchAgentDeliveryStatus(StrEnum):
    """Per-recipient delivery status for one agent message."""

    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchAgentMessageDelivery(BaseModel):
    """Immutable delivery state for one message recipient."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    delivery_id: str
    message_id: str
    recipient_agent_id: str
    status: ResearchAgentDeliveryStatus = (
        ResearchAgentDeliveryStatus.PENDING
    )
    attempt_count: int = Field(
        default=0,
        ge=0,
    )
    failure_reason: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    delivered_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_delivery(self) -> Self:
        """Validate delivery identity and lifecycle semantics."""

        required_text = {
            "delivery_id": self.delivery_id,
            "message_id": self.message_id,
            "recipient_agent_id": self.recipient_agent_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.failure_reason is not None
            and not self.failure_reason.strip()
        ):
            raise ValueError(
                "failure_reason must not be blank when provided"
            )

        self._validate_status_semantics()
        self._validate_timestamps()
        self._validate_metadata()

        return self

    def _validate_status_semantics(self) -> None:
        """Validate fields required by each delivery state."""

        if (
            self.status
            is ResearchAgentDeliveryStatus.FAILED
            and self.failure_reason is None
        ):
            raise ValueError(
                "failed delivery must include failure_reason"
            )

        if (
            self.status
            is not ResearchAgentDeliveryStatus.FAILED
            and self.failure_reason is not None
        ):
            raise ValueError(
                "non-failed delivery must not include "
                "failure_reason"
            )

        if (
            self.status
            in {
                ResearchAgentDeliveryStatus.DELIVERED,
                ResearchAgentDeliveryStatus.PROCESSING,
                ResearchAgentDeliveryStatus.ACKNOWLEDGED,
            }
            and self.delivered_at is None
        ):
            raise ValueError(
                "delivered delivery state must include "
                "delivered_at"
            )

        if (
            self.status
            in {
                ResearchAgentDeliveryStatus.ACKNOWLEDGED,
                ResearchAgentDeliveryStatus.FAILED,
                ResearchAgentDeliveryStatus.CANCELLED,
            }
            and self.completed_at is None
        ):
            raise ValueError(
                "terminal delivery state must include "
                "completed_at"
            )

    def _validate_timestamps(self) -> None:
        """Validate chronological delivery timestamps."""

        if (
            self.delivered_at is not None
            and self.delivered_at < self.created_at
        ):
            raise ValueError(
                "delivered_at must not precede created_at"
            )

        if (
            self.completed_at is not None
            and self.completed_at < self.created_at
        ):
            raise ValueError(
                "completed_at must not precede created_at"
            )

        if (
            self.delivered_at is not None
            and self.completed_at is not None
            and self.completed_at < self.delivered_at
        ):
            raise ValueError(
                "completed_at must not precede delivered_at"
            )

    def _validate_metadata(self) -> None:
        """Validate delivery metadata."""

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
    def is_terminal(self) -> bool:
        """Return whether delivery processing has ended."""

        return self.status in {
            ResearchAgentDeliveryStatus.ACKNOWLEDGED,
            ResearchAgentDeliveryStatus.FAILED,
            ResearchAgentDeliveryStatus.CANCELLED,
        }


class ResearchAgentReceivedMessage(BaseModel):
    """Message and delivery returned to one receiving agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    message: ResearchAgentMessage
    delivery: ResearchAgentMessageDelivery

    @model_validator(mode="after")
    def validate_received_message(self) -> Self:
        """Validate message and delivery consistency."""

        if (
            self.message.message_id.strip().casefold()
            != self.delivery.message_id.strip().casefold()
        ):
            raise ValueError(
                "delivery message_id must match message"
            )

        if not self.message.broadcast:
            recipient = self.message.recipient

            if recipient is None:
                raise ValueError(
                    "direct received message must have recipient"
                )

            if (
                recipient.agent_id.strip().casefold()
                != self.delivery.recipient_agent_id
                .strip()
                .casefold()
            ):
                raise ValueError(
                    "delivery recipient must match "
                    "message recipient"
                )

        return self


class ResearchAgentMessageBus(ABC):
    """Abstract contract for agent message transport."""

    @abstractmethod
    def publish(
        self,
        message: ResearchAgentMessage,
    ) -> list[ResearchAgentMessageDelivery]:
        """Publish a message and return created deliveries."""

    @abstractmethod
    def receive(
        self,
        agent_id: str,
        *,
        limit: int = 1,
    ) -> list[ResearchAgentReceivedMessage]:
        """Receive pending messages addressed to one agent."""

    @abstractmethod
    def start_processing(
        self,
        delivery_id: str,
        *,
        agent_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Mark a delivered message as being processed."""

    @abstractmethod
    def acknowledge(
        self,
        delivery_id: str,
        *,
        agent_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Acknowledge successful processing of a delivery."""

    @abstractmethod
    def fail(
        self,
        delivery_id: str,
        *,
        agent_id: str,
        reason: str,
    ) -> ResearchAgentMessageDelivery:
        """Record terminal processing failure for a delivery."""

    @abstractmethod
    def cancel(
        self,
        delivery_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Cancel one nonterminal delivery."""

    @abstractmethod
    def message(
        self,
        message_id: str,
    ) -> ResearchAgentMessage | None:
        """Return one published message by ID."""

    @abstractmethod
    def delivery(
        self,
        delivery_id: str,
    ) -> ResearchAgentMessageDelivery | None:
        """Return one delivery by ID."""

    @abstractmethod
    def deliveries_for_message(
        self,
        message_id: str,
    ) -> list[ResearchAgentMessageDelivery]:
        """Return all recipient deliveries for one message."""

    @abstractmethod
    def pending_count(
        self,
        agent_id: str,
    ) -> int:
        """Return pending delivery count for one agent."""

    @abstractmethod
    def correlation_history(
        self,
        correlation_id: str,
    ) -> list[ResearchAgentMessage]:
        """Return messages sharing one correlation ID."""
