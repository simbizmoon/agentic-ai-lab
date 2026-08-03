"""Operational reports for agent trace maintenance."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceStatus,
)


class AgentTraceMaintenanceReport(BaseModel):
    """Human-readable operational maintenance report."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    status: AgentTraceMaintenanceStatus
    headline: str
    details: list[str] = Field(min_length=1)

    archived_file_count: int = Field(ge=0)
    scanned_file_count: int = Field(ge=0)
    deleted_file_count: int = Field(ge=0)
    error_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_report(
        self,
    ) -> AgentTraceMaintenanceReport:
        """Validate report text and counts."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if not self.headline.strip():
            raise ValueError(
                "headline must not be blank"
            )

        if any(
            not detail.strip()
            for detail in self.details
        ):
            raise ValueError(
                "report details must not be blank"
            )

        return self
