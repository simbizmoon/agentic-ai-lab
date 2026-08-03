"""Schemas for exporting readable planning-agent traces."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)


class AgentTraceExportFormat(StrEnum):
    """Supported trace export formats."""

    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"


class AgentTraceExportResult(BaseModel):
    """One serialized trace export."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    format: AgentTraceExportFormat
    content: str
    media_type: str
    file_extension: str

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceExportResult:
        """Validate export identifiers and content."""

        required_text = {
            "trace_id": self.trace_id,
            "content": self.content,
            "media_type": self.media_type,
            "file_extension": self.file_extension,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if not self.file_extension.startswith("."):
            raise ValueError(
                "file_extension must start with a dot"
            )

        return self
