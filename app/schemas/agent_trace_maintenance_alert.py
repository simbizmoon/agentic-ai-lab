"""Alert decisions for agent trace maintenance."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class AgentTraceMaintenanceAlertSeverity(StrEnum):
    """Operational severity for maintenance alerts."""

    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"


class AgentTraceMaintenanceAlertCode(StrEnum):
    """Machine-readable maintenance alert codes."""

    ARCHIVE_STAGE_FAILED = "archive_stage_failed"
    RETENTION_STAGE_FAILED = "retention_stage_failed"
    MULTIPLE_STAGES_FAILED = "multiple_stages_failed"


class AgentTraceMaintenanceAlert(BaseModel):
    """Alert evaluation result for one maintenance run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    required: bool
    severity: AgentTraceMaintenanceAlertSeverity
    codes: list[AgentTraceMaintenanceAlertCode] = Field(
        default_factory=list
    )
    message: str

    @model_validator(mode="after")
    def validate_alert(
        self,
    ) -> AgentTraceMaintenanceAlert:
        """Validate alert consistency."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "alert message must not be blank"
            )

        if len(self.codes) != len(set(self.codes)):
            raise ValueError(
                "alert codes must be unique"
            )

        if self.required:
            if (
                self.severity
                is AgentTraceMaintenanceAlertSeverity.NONE
            ):
                raise ValueError(
                    "required alert must have a severity"
                )

            if not self.codes:
                raise ValueError(
                    "required alert must contain codes"
                )
        else:
            if (
                self.severity
                is not AgentTraceMaintenanceAlertSeverity.NONE
            ):
                raise ValueError(
                    "non-required alert must have NONE severity"
                )

            if self.codes:
                raise ValueError(
                    "non-required alert must not contain codes"
                )

        return self
