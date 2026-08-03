"""Operational results for agent trace maintenance."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
)
from app.schemas.agent_trace_maintenance_report import (
    AgentTraceMaintenanceReport,
)


class AgentTraceMaintenanceOperationsResult(BaseModel):
    """Combined maintenance, report, and alert result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    maintenance: AgentTraceMaintenanceResult
    report: AgentTraceMaintenanceReport
    alert: AgentTraceMaintenanceAlert

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceMaintenanceOperationsResult:
        """Validate consistency across operational views."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        trace_ids = {
            self.maintenance.trace_id,
            self.report.trace_id,
            self.alert.trace_id,
        }

        if trace_ids != {self.trace_id}:
            raise ValueError(
                "all operations trace IDs must match"
            )

        if self.report.status is not self.maintenance.status:
            raise ValueError(
                "report status must match maintenance status"
            )

        if (
            self.maintenance.errors
            and not self.alert.required
        ):
            raise ValueError(
                "maintenance errors require an alert"
            )

        if (
            not self.maintenance.errors
            and self.alert.required
        ):
            raise ValueError(
                "successful maintenance must not require "
                "an alert"
            )

        return self
