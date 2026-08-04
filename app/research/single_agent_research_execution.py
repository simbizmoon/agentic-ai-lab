"""Normalized result for one single-agent research execution."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_agent_result import (
    ResearchAgentTaskResult,
)


class SingleAgentResearchExecution(BaseModel):
    """Complete normalized single-agent research execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    result: ResearchAgentTaskResult
    execution_step_count: int = Field(default=1, ge=1)
    revision_round_count: int = Field(default=0, ge=0)
    traceable_source_count: int = Field(default=0, ge=0)
    traceable_evidence_count: int = Field(default=0, ge=0)
    traceable_claim_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        """Validate execution identity and metadata."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        if not self.workspace_id.strip():
            raise ValueError(
                "workspace_id must not be blank"
            )

        if (
            self.result.assignment.request_id
            != self.request_id
        ):
            raise ValueError(
                "result assignment must share request_id"
            )

        if (
            self.result.assignment.workspace_id
            != self.workspace_id
        ):
            raise ValueError(
                "result assignment must share workspace_id"
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
