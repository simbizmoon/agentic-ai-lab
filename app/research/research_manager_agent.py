"""Deterministic manager for dispatching research-agent assignments."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.research.research_agent_message_bus import (
    ResearchAgentMessageBus,
    ResearchAgentMessageDelivery,
)
from app.research.research_agent_registry import (
    ResearchAgentRegistry,
)
from app.research.research_manager_agent_error import (
    ResearchManagerAgentError,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentPriority,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
    ResearchAgentMessagePriority,
    ResearchAgentMessageStatus,
    ResearchAgentMessageType,
)


class ResearchManagerDispatch(BaseModel):
    """Assignment, message, and deliveries created by one dispatch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    assignment: ResearchAgentTaskAssignment
    message: ResearchAgentMessage
    deliveries: list[
        ResearchAgentMessageDelivery
    ] = Field(min_length=1)


class ResearchManagerAgent:
    """Select a specialist and dispatch one research assignment."""

    def __init__(
        self,
        *,
        manager_agent_id: str,
        registry: ResearchAgentRegistry,
        message_bus: ResearchAgentMessageBus,
        now: Callable[[], datetime] | None = None,
        assignment_id_factory: Callable[[], str] | None = None,
        message_id_factory: Callable[[], str] | None = None,
        correlation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not manager_agent_id.strip():
            raise ValueError(
                "manager_agent_id must not be blank"
            )

        self._registry = registry
        self._message_bus = message_bus
        self._now = now or (
            lambda: datetime.now(UTC)
        )
        self._assignment_id_factory = (
            assignment_id_factory
            or (
                lambda: (
                    f"assignment-{uuid4()}"
                )
            )
        )
        self._message_id_factory = (
            message_id_factory
            or (
                lambda: (
                    f"message-{uuid4()}"
                )
            )
        )
        self._correlation_id_factory = (
            correlation_id_factory
            or (
                lambda: (
                    f"correlation-{uuid4()}"
                )
            )
        )

        self._manager = self._registry.require_agent(
            manager_agent_id
        )
        self._manager_profile = (
            self._registry.require_profile_for_agent(
                manager_agent_id
            )
        )

        if (
            self._manager.role
            is not ResearchAgentRole.MANAGER
        ):
            raise ResearchManagerAgentError(
                "manager agent must have manager role"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return the manager agent identity."""

        return self._manager

    def dispatch(
        self,
        *,
        request_id: str,
        workspace_id: str,
        required_role: ResearchAgentRole,
        required_capabilities: list[
            ResearchAgentCapability
        ],
        title: str,
        objective: str,
        instructions: list[str],
        expected_output_type: str,
        acceptance_criteria: list[str],
        research_task_id: str | None = None,
        inputs: list[
            ResearchAgentAssignmentInput
        ] | None = None,
        assignment_priority: (
            ResearchAgentAssignmentPriority
        ) = ResearchAgentAssignmentPriority.NORMAL,
        message_priority: (
            ResearchAgentMessagePriority
        ) = ResearchAgentMessagePriority.NORMAL,
        maximum_attempts: int = 1,
        parent_assignment_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ResearchManagerDispatch:
        """Select a qualified specialist and dispatch work."""

        self._validate_required_text(
            request_id,
            field_name="request_id",
        )
        self._validate_required_text(
            workspace_id,
            field_name="workspace_id",
        )
        self._validate_required_text(
            title,
            field_name="title",
        )
        self._validate_required_text(
            objective,
            field_name="objective",
        )
        self._validate_required_text(
            expected_output_type,
            field_name="expected_output_type",
        )

        self._validate_unique_capabilities(
            required_capabilities
        )

        assignee = self._select_assignee(
            required_role=required_role,
            required_capabilities=required_capabilities,
        )

        timestamp = self._now()
        assignment_id = self._new_identifier(
            self._assignment_id_factory,
            field_name="assignment_id",
        )
        message_id = self._new_identifier(
            self._message_id_factory,
            field_name="message_id",
        )
        resolved_correlation_id = (
            correlation_id
            if correlation_id is not None
            else self._new_identifier(
                self._correlation_id_factory,
                field_name="correlation_id",
            )
        )

        self._validate_required_text(
            resolved_correlation_id,
            field_name="correlation_id",
        )

        assignment = ResearchAgentTaskAssignment(
            assignment_id=assignment_id,
            request_id=request_id,
            workspace_id=workspace_id,
            research_task_id=research_task_id,
            assigner_profile=self._manager_profile,
            assignee=assignee,
            required_role=required_role,
            required_capabilities=(
                required_capabilities
            ),
            title=title,
            objective=objective,
            instructions=instructions,
            inputs=inputs or [],
            expected_output_type=expected_output_type,
            acceptance_criteria=acceptance_criteria,
            priority=assignment_priority,
            status=(
                ResearchAgentAssignmentStatus.OFFERED
            ),
            attempt_number=1,
            maximum_attempts=maximum_attempts,
            parent_assignment_id=parent_assignment_id,
            created_at=timestamp,
            metadata=metadata or {},
        )

        message = ResearchAgentMessage(
            message_id=message_id,
            message_type=(
                ResearchAgentMessageType.TASK_REQUEST
            ),
            sender=self._manager,
            recipient=assignee,
            broadcast=False,
            correlation_id=resolved_correlation_id,
            assignment_id=assignment.assignment_id,
            request_id=request_id,
            workspace_id=workspace_id,
            subject=title,
            payload={
                "assignment_id": assignment.assignment_id,
                "required_role": required_role.value,
                "required_capabilities": [
                    capability.value
                    for capability
                    in required_capabilities
                ],
                "expected_output_type": (
                    expected_output_type
                ),
                "maximum_attempts": maximum_attempts,
            },
            priority=message_priority,
            status=ResearchAgentMessageStatus.CREATED,
            created_at=timestamp,
            metadata=metadata or {},
        )

        deliveries = self._message_bus.publish(message)

        if not deliveries:
            raise ResearchManagerAgentError(
                "task request produced no message delivery"
            )

        return ResearchManagerDispatch(
            assignment=assignment,
            message=message,
            deliveries=deliveries,
        )

    def _select_assignee(
        self,
        *,
        required_role: ResearchAgentRole,
        required_capabilities: list[
            ResearchAgentCapability
        ],
    ) -> ResearchAgentIdentity:
        """Return the first available qualified delegation target."""

        targets = self._registry.delegation_targets(
            self._manager.agent_id,
            required_role,
            available_only=True,
        )

        for target in targets:
            profile = (
                self._registry.profile_for_agent(
                    target.agent_id
                )
            )

            if profile is None:
                continue

            if all(
                profile.has_capability(capability)
                for capability
                in required_capabilities
            ):
                return target

        raise ResearchManagerAgentError(
            "no available qualified agent "
            "for requested role and capabilities"
        )

    @staticmethod
    def _validate_required_text(
        value: str,
        *,
        field_name: str,
    ) -> None:
        """Validate one required text value."""

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be blank"
            )

    @staticmethod
    def _validate_unique_capabilities(
        capabilities: list[
            ResearchAgentCapability
        ],
    ) -> None:
        """Validate required capability uniqueness."""

        values = [
            capability.value
            for capability in capabilities
        ]

        if len(set(values)) != len(values):
            raise ValueError(
                "required_capabilities must not "
                "contain duplicates"
            )

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate and validate one identifier."""

        value = factory()

        if not value.strip():
            raise ResearchManagerAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
