"""Output snapshot supplied to research result guardrails."""

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
from app.schemas.research_agent_result import (
    ResearchAgentTaskResult,
)


class OutputGuardrailSnapshot(BaseModel):
    """Agent result and expected execution context."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    result: ResearchAgentTaskResult
    expected_assignment: ResearchAgentTaskAssignment
    expected_request_id: str
    expected_workspace_id: str
    require_primary_output: bool = True
    require_exactly_one_primary_output: bool = True
    enforce_expected_output_type: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate expected output context."""

        if not self.expected_request_id.strip():
            raise ValueError(
                "expected_request_id must not be blank"
            )

        if not self.expected_workspace_id.strip():
            raise ValueError(
                "expected_workspace_id must not be blank"
            )

        if (
            self.require_exactly_one_primary_output
            and not self.require_primary_output
        ):
            raise ValueError(
                "exactly-one primary output requires "
                "require_primary_output"
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
