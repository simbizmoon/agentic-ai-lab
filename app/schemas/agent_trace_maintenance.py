"""Results from trace archive and retention maintenance."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionResult,
)


class AgentTraceMaintenanceResult(BaseModel):
    """Combined result of trace archiving and retention."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    archive: AgentTracePolicyArchiveResult
    retention: AgentTraceRetentionResult

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceMaintenanceResult:
        """Validate maintenance-result consistency."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if self.archive.trace_id != self.trace_id:
            raise ValueError(
                "archive trace_id must match maintenance trace_id"
            )

        return self
