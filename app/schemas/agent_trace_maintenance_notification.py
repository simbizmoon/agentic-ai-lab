"""Results from maintenance operations and alert notification."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationResult,
)
from app.schemas.agent_trace_maintenance_operations import (
    AgentTraceMaintenanceOperationsResult,
)


class AgentTraceMaintenanceNotificationResult(BaseModel):
    """Combined maintenance operations and notification result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    operations: AgentTraceMaintenanceOperationsResult
    notification: AgentTraceAlertNotificationResult

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceMaintenanceNotificationResult:
        """Validate trace identifiers and notification state."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        trace_ids = {
            self.operations.trace_id,
            self.notification.trace_id,
        }

        if trace_ids != {self.trace_id}:
            raise ValueError(
                "all notification trace IDs must match"
            )

        return self
