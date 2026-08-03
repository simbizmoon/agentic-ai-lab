"""Results from policy-driven agent trace archiving."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_file import (
    AgentTraceFileWriteResult,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)


class AgentTracePolicyArchiveResult(BaseModel):
    """Result of evaluating and applying an archive policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    outcome: AgentTraceOutcome
    archived: bool
    files: list[AgentTraceFileWriteResult] = Field(
        default_factory=list
    )
    reason: str

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTracePolicyArchiveResult:
        """Validate archive-result consistency."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if not self.reason.strip():
            raise ValueError(
                "reason must not be blank"
            )

        if self.archived and not self.files:
            raise ValueError(
                "archived result must contain files"
            )

        if not self.archived and self.files:
            raise ValueError(
                "non-archived result must not contain files"
            )

        formats = [
            file.format
            for file in self.files
        ]

        if len(formats) != len(set(formats)):
            raise ValueError(
                "archived file formats must be unique"
            )

        return self
