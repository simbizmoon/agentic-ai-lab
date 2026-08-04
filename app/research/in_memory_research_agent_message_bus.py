"""In-memory implementation of the research-agent message bus."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.research.research_agent_message_bus import (
    ResearchAgentDeliveryStatus,
    ResearchAgentMessageBus,
    ResearchAgentMessageDelivery,
    ResearchAgentReceivedMessage,
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
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
)


class InMemoryResearchAgentMessageBus(
    ResearchAgentMessageBus
):
    """Store and deliver research-agent messages in memory."""

    def __init__(
        self,
        *,
        registry: ResearchAgentRegistry,
        now: Callable[[], datetime] | None = None,
        delivery_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._registry = registry
        self._now = now or (
            lambda: datetime.now(UTC)
        )
        self._delivery_id_factory = (
            delivery_id_factory
            or (lambda: f"delivery-{uuid4()}")
        )

        self._messages: dict[
            str,
            ResearchAgentMessage,
        ] = {}
        self._deliveries: dict[
            str,
            ResearchAgentMessageDelivery,
        ] = {}
        self._message_delivery_ids: dict[
            str,
            list[str],
        ] = {}
        self._recipient_delivery_ids: dict[
            str,
            list[str],
        ] = {}
        self._publish_order: dict[str, int] = {}
        self._next_publish_order = 0

    @staticmethod
    def _normalize_identifier(
        value: str,
        *,
        field_name: str,
    ) -> str:
        """Normalize one required identifier."""

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be blank"
            )

        return value.strip().casefold()

    def publish(
        self,
        message: ResearchAgentMessage,
    ) -> list[ResearchAgentMessageDelivery]:
        """Publish a message and create recipient deliveries."""

        message_key = self._normalize_identifier(
            message.message_id,
            field_name="message_id",
        )

        if message_key in self._messages:
            raise ResearchAgentMessageAlreadyExistsError(
                "message ID has already been published"
            )

        self._require_registered_agent(
            message.sender.agent_id
        )

        recipients = self._resolve_recipients(message)

        self._messages[message_key] = message
        self._publish_order[message_key] = (
            self._next_publish_order
        )
        self._next_publish_order += 1
        self._message_delivery_ids[message_key] = []

        created_deliveries: list[
            ResearchAgentMessageDelivery
        ] = []

        for recipient_agent_id in recipients:
            delivery = self._create_delivery(
                message=message,
                recipient_agent_id=recipient_agent_id,
            )
            created_deliveries.append(delivery)

        return list(created_deliveries)

    def _resolve_recipients(
        self,
        message: ResearchAgentMessage,
    ) -> list[str]:
        """Return registered recipient IDs for one message."""

        if message.broadcast:
            sender_key = self._normalize_identifier(
                message.sender.agent_id,
                field_name="sender agent_id",
            )

            return [
                agent.agent_id
                for agent in self._registry.agents()
                if self._normalize_identifier(
                    agent.agent_id,
                    field_name="agent_id",
                )
                != sender_key
            ]

        recipient = message.recipient

        if recipient is None:
            raise ValueError(
                "direct message must define recipient"
            )

        registered_recipient = (
            self._require_registered_agent(
                recipient.agent_id
            )
        )

        if registered_recipient != recipient:
            raise ResearchAgentRegistryError(
                "message recipient must match "
                "registered agent"
            )

        return [registered_recipient.agent_id]

    def _require_registered_agent(
        self,
        agent_id: str,
    ):
        """Return a registered agent or propagate registry error."""

        return self._registry.require_agent(agent_id)

    def _create_delivery(
        self,
        *,
        message: ResearchAgentMessage,
        recipient_agent_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Create and store one pending delivery."""

        delivery_id = self._delivery_id_factory()

        delivery_key = self._normalize_identifier(
            delivery_id,
            field_name="delivery_id",
        )

        if delivery_key in self._deliveries:
            raise ResearchAgentDeliveryStateError(
                "delivery ID has already been generated"
            )

        delivery = ResearchAgentMessageDelivery(
            delivery_id=delivery_id,
            message_id=message.message_id,
            recipient_agent_id=recipient_agent_id,
            status=ResearchAgentDeliveryStatus.PENDING,
            attempt_count=0,
            created_at=self._now(),
            metadata={
                "transport": "in-memory",
            },
        )

        message_key = self._normalize_identifier(
            message.message_id,
            field_name="message_id",
        )
        recipient_key = self._normalize_identifier(
            recipient_agent_id,
            field_name="recipient_agent_id",
        )

        self._deliveries[delivery_key] = delivery
        self._message_delivery_ids[
            message_key
        ].append(delivery_key)
        self._recipient_delivery_ids.setdefault(
            recipient_key,
            [],
        ).append(delivery_key)

        return delivery

    def receive(
        self,
        agent_id: str,
        *,
        limit: int = 1,
    ) -> list[ResearchAgentReceivedMessage]:
        """Deliver pending messages to one registered agent."""

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero"
            )

        registered_agent = (
            self._require_registered_agent(agent_id)
        )
        agent_key = self._normalize_identifier(
            registered_agent.agent_id,
            field_name="agent_id",
        )

        pending_deliveries = [
            self._deliveries[delivery_id]
            for delivery_id
            in self._recipient_delivery_ids.get(
                agent_key,
                [],
            )
            if (
                self._deliveries[delivery_id].status
                is ResearchAgentDeliveryStatus.PENDING
            )
        ]

        pending_deliveries.sort(
            key=self._delivery_sort_key
        )

        received: list[
            ResearchAgentReceivedMessage
        ] = []

        for delivery in pending_deliveries[:limit]:
            delivered = delivery.model_copy(
                update={
                    "status": (
                        ResearchAgentDeliveryStatus.DELIVERED
                    ),
                    "attempt_count": (
                        delivery.attempt_count + 1
                    ),
                    "delivered_at": self._now(),
                }
            )

            delivery_key = self._normalize_identifier(
                delivered.delivery_id,
                field_name="delivery_id",
            )
            self._deliveries[delivery_key] = delivered

            message = self._require_message(
                delivered.message_id
            )

            received.append(
                ResearchAgentReceivedMessage(
                    message=message,
                    delivery=delivered,
                )
            )

        return received

    def _delivery_sort_key(
        self,
        delivery: ResearchAgentMessageDelivery,
    ) -> tuple[int, int]:
        """Return deterministic priority and publication sort key."""

        message = self._require_message(
            delivery.message_id
        )
        message_key = self._normalize_identifier(
            message.message_id,
            field_name="message_id",
        )

        return (
            -int(message.priority),
            self._publish_order[message_key],
        )

    def start_processing(
        self,
        delivery_id: str,
        *,
        agent_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Move one delivered message into processing state."""

        delivery = self._require_delivery(delivery_id)
        self._validate_delivery_access(
            delivery,
            agent_id=agent_id,
        )

        if (
            delivery.status
            is not ResearchAgentDeliveryStatus.DELIVERED
        ):
            raise ResearchAgentDeliveryStateError(
                "only delivered message can start processing"
            )

        updated = delivery.model_copy(
            update={
                "status": (
                    ResearchAgentDeliveryStatus.PROCESSING
                ),
            }
        )
        self._store_delivery(updated)

        return updated

    def acknowledge(
        self,
        delivery_id: str,
        *,
        agent_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Acknowledge successful processing."""

        delivery = self._require_delivery(delivery_id)
        self._validate_delivery_access(
            delivery,
            agent_id=agent_id,
        )

        if (
            delivery.status
            is not ResearchAgentDeliveryStatus.PROCESSING
        ):
            raise ResearchAgentDeliveryStateError(
                "only processing delivery can be acknowledged"
            )

        updated = delivery.model_copy(
            update={
                "status": (
                    ResearchAgentDeliveryStatus.ACKNOWLEDGED
                ),
                "completed_at": self._now(),
            }
        )
        self._store_delivery(updated)

        return updated

    def fail(
        self,
        delivery_id: str,
        *,
        agent_id: str,
        reason: str,
    ) -> ResearchAgentMessageDelivery:
        """Record terminal processing failure."""

        if not reason.strip():
            raise ValueError(
                "reason must not be blank"
            )

        delivery = self._require_delivery(delivery_id)
        self._validate_delivery_access(
            delivery,
            agent_id=agent_id,
        )

        if (
            delivery.status
            is not ResearchAgentDeliveryStatus.PROCESSING
        ):
            raise ResearchAgentDeliveryStateError(
                "only processing delivery can fail"
            )

        updated = delivery.model_copy(
            update={
                "status": ResearchAgentDeliveryStatus.FAILED,
                "failure_reason": reason,
                "completed_at": self._now(),
            }
        )
        self._store_delivery(updated)

        return updated

    def cancel(
        self,
        delivery_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Cancel one nonterminal delivery."""

        delivery = self._require_delivery(delivery_id)

        if delivery.is_terminal:
            raise ResearchAgentDeliveryStateError(
                "terminal delivery cannot be cancelled"
            )

        updated = delivery.model_copy(
            update={
                "status": (
                    ResearchAgentDeliveryStatus.CANCELLED
                ),
                "completed_at": self._now(),
            }
        )
        self._store_delivery(updated)

        return updated

    def _validate_delivery_access(
        self,
        delivery: ResearchAgentMessageDelivery,
        *,
        agent_id: str,
    ) -> None:
        """Validate that an agent owns a delivery."""

        registered_agent = (
            self._require_registered_agent(agent_id)
        )

        requested_agent_key = (
            self._normalize_identifier(
                registered_agent.agent_id,
                field_name="agent_id",
            )
        )
        recipient_key = self._normalize_identifier(
            delivery.recipient_agent_id,
            field_name="recipient_agent_id",
        )

        if requested_agent_key != recipient_key:
            raise ResearchAgentDeliveryAccessError(
                "agent cannot access this delivery"
            )

    def _store_delivery(
        self,
        delivery: ResearchAgentMessageDelivery,
    ) -> None:
        """Replace one stored immutable delivery."""

        delivery_key = self._normalize_identifier(
            delivery.delivery_id,
            field_name="delivery_id",
        )
        self._deliveries[delivery_key] = delivery

    def message(
        self,
        message_id: str,
    ) -> ResearchAgentMessage | None:
        """Return one published message by normalized ID."""

        message_key = self._normalize_identifier(
            message_id,
            field_name="message_id",
        )

        return self._messages.get(message_key)

    def _require_message(
        self,
        message_id: str,
    ) -> ResearchAgentMessage:
        """Return one published message or raise."""

        message = self.message(message_id)

        if message is None:
            raise ResearchAgentMessageNotFoundError(
                "message was not found"
            )

        return message

    def delivery(
        self,
        delivery_id: str,
    ) -> ResearchAgentMessageDelivery | None:
        """Return one delivery by normalized ID."""

        delivery_key = self._normalize_identifier(
            delivery_id,
            field_name="delivery_id",
        )

        return self._deliveries.get(delivery_key)

    def _require_delivery(
        self,
        delivery_id: str,
    ) -> ResearchAgentMessageDelivery:
        """Return one delivery or raise."""

        delivery = self.delivery(delivery_id)

        if delivery is None:
            raise ResearchAgentDeliveryNotFoundError(
                "delivery was not found"
            )

        return delivery

    def deliveries_for_message(
        self,
        message_id: str,
    ) -> list[ResearchAgentMessageDelivery]:
        """Return all deliveries created for one message."""

        message = self._require_message(message_id)
        message_key = self._normalize_identifier(
            message.message_id,
            field_name="message_id",
        )

        return [
            self._deliveries[delivery_id]
            for delivery_id
            in self._message_delivery_ids[message_key]
        ]

    def pending_count(
        self,
        agent_id: str,
    ) -> int:
        """Return pending delivery count for one agent."""

        registered_agent = (
            self._require_registered_agent(agent_id)
        )
        agent_key = self._normalize_identifier(
            registered_agent.agent_id,
            field_name="agent_id",
        )

        return sum(
            self._deliveries[delivery_id].status
            is ResearchAgentDeliveryStatus.PENDING
            for delivery_id
            in self._recipient_delivery_ids.get(
                agent_key,
                [],
            )
        )

    def correlation_history(
        self,
        correlation_id: str,
    ) -> list[ResearchAgentMessage]:
        """Return messages in one correlation chain."""

        normalized = self._normalize_identifier(
            correlation_id,
            field_name="correlation_id",
        )

        matches = [
            message
            for message in self._messages.values()
            if (
                message.correlation_id
                .strip()
                .casefold()
                == normalized
            )
        ]

        matches.sort(
            key=lambda message: self._publish_order[
                self._normalize_identifier(
                    message.message_id,
                    field_name="message_id",
                )
            ]
        )

        return matches
