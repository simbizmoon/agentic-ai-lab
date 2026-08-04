"""Schemas for assigning research work to specialist agents."""

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

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)


class ResearchAgentAssignmentStatus(StrEnum):
    """Lifecycle status of one agent task assignment."""

    CREATED = "created"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ResearchAgentAssignmentPriority(IntEnum):
    """Priority used to order task assignments."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    CRITICAL = 40


class ResearchAgentAssignmentInput(BaseModel):
    """One structured input reference for an assignment."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    name: str
    reference_type: str
    reference_id: str
    required: bool = True
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        """Validate assignment input reference."""

        required_text = {
            "name": self.name,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class ResearchAgentTaskAssignment(BaseModel):
    """Immutable assignment of one research task to one agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    assignment_id: str
    request_id: str
    workspace_id: str
    research_task_id: str | None = None
    assigner_profile: ResearchAgentCapabilityProfile
    assignee: ResearchAgentIdentity
    required_role: ResearchAgentRole
    required_capabilities: list[
        ResearchAgentCapability
    ] = Field(default_factory=list)
    title: str
    objective: str
    instructions: list[str] = Field(
        min_length=1
    )
    inputs: list[
        ResearchAgentAssignmentInput
    ] = Field(default_factory=list)
    expected_output_type: str
    acceptance_criteria: list[str] = Field(
        min_length=1
    )
    payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    priority: ResearchAgentAssignmentPriority = (
        ResearchAgentAssignmentPriority.NORMAL
    )
    status: ResearchAgentAssignmentStatus = (
        ResearchAgentAssignmentStatus.CREATED
    )
    attempt_number: int = Field(
        default=1,
        ge=1,
    )
    maximum_attempts: int = Field(
        default=1,
        ge=1,
    )
    parent_assignment_id: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_assignment(self) -> Self:
        """Validate assignment identity and delegation rules."""

        required_text = {
            "assignment_id": self.assignment_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "objective": self.objective,
            "expected_output_type": (
                self.expected_output_type
            ),
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_optional_identifier(
            self.research_task_id,
            field_name="research_task_id",
        )
        self._validate_optional_identifier(
            self.parent_assignment_id,
            field_name="parent_assignment_id",
        )

        self._validate_agent_relationship()
        self._validate_required_capabilities()
        self._validate_unique_text(
            self.instructions,
            field_name="instructions",
        )
        self._validate_inputs()
        self._validate_unique_text(
            self.acceptance_criteria,
            field_name="acceptance_criteria",
        )
        self._validate_attempts()
        self._validate_payload()
        self._validate_metadata()

        return self

    @staticmethod
    def _validate_optional_identifier(
        value: str | None,
        *,
        field_name: str,
    ) -> None:
        """Validate one optional identifier."""

        if value is not None and not value.strip():
            raise ValueError(
                f"{field_name} must not be blank when provided"
            )

    def _validate_agent_relationship(self) -> None:
        """Validate assigner, assignee, and required role."""

        assigner = self.assigner_profile.agent

        if (
            assigner.agent_id.strip().casefold()
            == self.assignee.agent_id.strip().casefold()
        ):
            raise ValueError(
                "assigner and assignee must be different agents"
            )

        if self.assignee.role is not self.required_role:
            raise ValueError(
                "assignee role must match required_role"
            )

        if not self.assigner_profile.can_delegate_to(
            self.required_role
        ):
            raise ValueError(
                "assigner is not permitted to delegate "
                "to required_role"
            )

    def _validate_required_capabilities(self) -> None:
        """Validate required capability collection."""

        capability_values = [
            capability.value
            for capability in self.required_capabilities
        ]

        if len(set(capability_values)) != len(
            capability_values
        ):
            raise ValueError(
                "required_capabilities must not "
                "contain duplicates"
            )

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique text entries."""

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    def _validate_inputs(self) -> None:
        """Validate assignment input uniqueness."""

        input_keys = [
            (
                item.reference_type.strip().casefold(),
                item.reference_id.strip().casefold(),
            )
            for item in self.inputs
        ]

        if len(set(input_keys)) != len(input_keys):
            raise ValueError(
                "assignment inputs must not contain "
                "duplicate references"
            )

    def _validate_attempts(self) -> None:
        """Validate attempt count limits."""

        if self.attempt_number > self.maximum_attempts:
            raise ValueError(
                "attempt_number must not exceed "
                "maximum_attempts"
            )

    def _validate_payload(self) -> None:
        """Validate structured payload keys."""

        if any(
            not key.strip()
            for key in self.payload
        ):
            raise ValueError(
                "payload keys must not be blank"
            )

    def _validate_metadata(self) -> None:
        """Validate assignment metadata."""

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
        """Return whether assignment processing has ended."""

        return self.status in {
            ResearchAgentAssignmentStatus.COMPLETED,
            ResearchAgentAssignmentStatus.FAILED,
            ResearchAgentAssignmentStatus.REJECTED,
            ResearchAgentAssignmentStatus.CANCELLED,
        }

    @property
    def can_retry(self) -> bool:
        """Return whether another attempt is allowed."""

        return (
            self.status
            is ResearchAgentAssignmentStatus.FAILED
            and self.attempt_number < self.maximum_attempts
        )

    def requires_capability(
        self,
        capability: ResearchAgentCapability,
    ) -> bool:
        """Return whether the assignment requires a capability."""

        return capability in self.required_capabilities

    def input_by_name(
        self,
        name: str,
    ) -> ResearchAgentAssignmentInput | None:
        """Return one assignment input by normalized name."""

        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        normalized = name.strip().casefold()

        return next(
            (
                item
                for item in self.inputs
                if item.name.strip().casefold()
                == normalized
            ),
            None,
        )
