"""Archive policies for recorded planning-agent traces."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)


class AgentTraceArchivePolicy(BaseModel):
    """Configuration controlling automatic trace archiving."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    formats: list[AgentTraceExportFormat] = Field(
        min_length=1
    )

    archive_completed: bool = True
    archive_failed: bool = True
    archive_incomplete: bool = False
    overwrite: bool = False

    @model_validator(mode="after")
    def validate_policy(
        self,
    ) -> AgentTraceArchivePolicy:
        """Reject duplicate formats and unusable policies."""

        if len(self.formats) != len(set(self.formats)):
            raise ValueError(
                "archive formats must be unique"
            )

        if not any(
            (
                self.archive_completed,
                self.archive_failed,
                self.archive_incomplete,
            )
        ):
            raise ValueError(
                "archive policy must enable at least one outcome"
            )

        return self
