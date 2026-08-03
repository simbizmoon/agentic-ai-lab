"""Results from trace archive and retention maintenance."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionResult,
)


class AgentTraceMaintenanceStatus(StrEnum):
    """Overall outcome of trace maintenance."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class AgentTraceMaintenanceStage(StrEnum):
    """Individual stage in trace maintenance."""

    ARCHIVE = "archive"
    RETENTION = "retention"


class AgentTraceMaintenanceError(BaseModel):
    """Structured failure from one maintenance stage."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    stage: AgentTraceMaintenanceStage
    error_type: str
    message: str

    @model_validator(mode="after")
    def validate_error(
        self,
    ) -> AgentTraceMaintenanceError:
        """Reject blank error descriptions."""

        if not self.error_type.strip():
            raise ValueError(
                "error_type must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "error message must not be blank"
            )

        return self


class AgentTraceMaintenanceResult(BaseModel):
    """Combined result of trace archiving and retention."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    status: AgentTraceMaintenanceStatus

    archive: AgentTracePolicyArchiveResult | None = None
    retention: AgentTraceRetentionResult | None = None

    errors: list[AgentTraceMaintenanceError] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceMaintenanceResult:
        """Validate maintenance-result consistency."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if (
            self.archive is not None
            and self.archive.trace_id != self.trace_id
        ):
            raise ValueError(
                "archive trace_id must match maintenance trace_id"
            )

        successful_stage_count = sum(
            (
                self.archive is not None,
                self.retention is not None,
            )
        )

        if self.status is AgentTraceMaintenanceStatus.SUCCESS:
            if successful_stage_count != 2:
                raise ValueError(
                    "successful maintenance must contain "
                    "archive and retention results"
                )

            if self.errors:
                raise ValueError(
                    "successful maintenance must not "
                    "contain errors"
                )

        elif (
            self.status
            is AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
        ):
            if successful_stage_count != 1:
                raise ValueError(
                    "partial maintenance must contain "
                    "exactly one successful stage"
                )

            if len(self.errors) != 1:
                raise ValueError(
                    "partial maintenance must contain "
                    "exactly one error"
                )

        elif self.status is AgentTraceMaintenanceStatus.FAILED:
            if successful_stage_count != 0:
                raise ValueError(
                    "failed maintenance must not contain "
                    "successful stage results"
                )

            if len(self.errors) != 2:
                raise ValueError(
                    "failed maintenance must contain "
                    "two stage errors"
                )

        error_stages = [
            error.stage
            for error in self.errors
        ]

        if len(error_stages) != len(set(error_stages)):
            raise ValueError(
                "maintenance error stages must be unique"
            )

        if (
            self.archive is not None
            and AgentTraceMaintenanceStage.ARCHIVE
            in error_stages
        ):
            raise ValueError(
                "archive stage cannot have both result and error"
            )

        if (
            self.retention is not None
            and AgentTraceMaintenanceStage.RETENTION
            in error_stages
        ):
            raise ValueError(
                "retention stage cannot have both result and error"
            )

        return self
