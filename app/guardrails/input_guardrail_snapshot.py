"""Input snapshot supplied to assignment guardrails."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapabilityProfile,
)


class InputGuardrailSnapshot(BaseModel):
    """Assignment and runtime context checked before execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    assignment: ResearchAgentTaskAssignment
    assignee_profile: ResearchAgentCapabilityProfile
    available_reference_ids: list[str] = Field(
        default_factory=list
    )
    expected_request_id: str
    expected_workspace_id: str
    require_inputs: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate snapshot context and reference uniqueness."""

        if not self.expected_request_id.strip():
            raise ValueError(
                "expected_request_id must not be blank"
            )

        if not self.expected_workspace_id.strip():
            raise ValueError(
                "expected_workspace_id must not be blank"
            )

        if any(
            not reference_id.strip()
            for reference_id in self.available_reference_ids
        ):
            raise ValueError(
                "available_reference_ids must not contain "
                "blank values"
            )

        normalized = [
            reference_id.strip().casefold()
            for reference_id in self.available_reference_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "available_reference_ids must not contain "
                "duplicates"
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
