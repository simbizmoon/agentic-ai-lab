"""Schemas for writing exported agent traces to files."""

from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)


class AgentTraceFileWriteRequest(BaseModel):
    """Request for saving one exported trace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        arbitrary_types_allowed=True,
    )

    file_name: str | None = None
    overwrite: bool = False

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> AgentTraceFileWriteRequest:
        """Validate an optional custom file name."""

        if (
            self.file_name is not None
            and not self.file_name.strip()
        ):
            raise ValueError(
                "file_name must not be blank"
            )

        return self


class AgentTraceFileWriteResult(BaseModel):
    """Result of writing one trace export to disk."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        arbitrary_types_allowed=True,
    )

    trace_id: str
    format: AgentTraceExportFormat
    path: Path
    byte_count: int = Field(ge=0)
    overwritten: bool

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceFileWriteResult:
        """Validate identifiers and output path."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if not self.path.is_absolute():
            raise ValueError(
                "path must be absolute"
            )

        return self
