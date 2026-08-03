"""Operational maintenance for archived agent traces."""

from __future__ import annotations

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceError,
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStage,
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
    AgentTraceRetentionResult,
)
from app.tracing.agent_trace_policy_archive_service import (
    AgentTracePolicyArchiveService,
)
from app.tracing.agent_trace_retention_service import (
    AgentTraceRetentionService,
)


class AgentTraceMaintenanceService:
    """Archive one trace and independently apply retention."""

    def __init__(
        self,
        *,
        archive_service: AgentTracePolicyArchiveService,
        retention_service: AgentTraceRetentionService,
        retention_policy: AgentTraceRetentionPolicy,
    ) -> None:
        self._archive_service = archive_service
        self._retention_service = retention_service
        self._retention_policy = retention_policy

    @property
    def archive_service(
        self,
    ) -> AgentTracePolicyArchiveService:
        """Return the configured policy archive service."""

        return self._archive_service

    @property
    def retention_service(
        self,
    ) -> AgentTraceRetentionService:
        """Return the configured retention service."""

        return self._retention_service

    @property
    def retention_policy(
        self,
    ) -> AgentTraceRetentionPolicy:
        """Return the configured retention policy."""

        return self._retention_policy

    def maintain(
        self,
        trace_id: str,
    ) -> AgentTraceMaintenanceResult:
        """Run archive and retention as independent stages."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        archive_result: (
            AgentTracePolicyArchiveResult | None
        ) = None
        retention_result: (
            AgentTraceRetentionResult | None
        ) = None
        errors: list[AgentTraceMaintenanceError] = []

        try:
            archive_result = self.archive_service.archive(
                trace_id
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                self._error(
                    stage=(
                        AgentTraceMaintenanceStage.ARCHIVE
                    ),
                    exception=exc,
                )
            )

        try:
            retention_result = self.retention_service.apply(
                self.retention_policy
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                self._error(
                    stage=(
                        AgentTraceMaintenanceStage.RETENTION
                    ),
                    exception=exc,
                )
            )

        status = self._status(
            archive_result=archive_result,
            retention_result=retention_result,
        )

        return AgentTraceMaintenanceResult(
            trace_id=trace_id,
            status=status,
            archive=archive_result,
            retention=retention_result,
            errors=errors,
        )

    @staticmethod
    def _status(
        *,
        archive_result: (
            AgentTracePolicyArchiveResult | None
        ),
        retention_result: (
            AgentTraceRetentionResult | None
        ),
    ) -> AgentTraceMaintenanceStatus:
        """Derive the overall status from stage results."""

        successful_stage_count = sum(
            (
                archive_result is not None,
                retention_result is not None,
            )
        )

        if successful_stage_count == 2:
            return AgentTraceMaintenanceStatus.SUCCESS

        if successful_stage_count == 1:
            return (
                AgentTraceMaintenanceStatus
                .PARTIAL_SUCCESS
            )

        return AgentTraceMaintenanceStatus.FAILED

    @staticmethod
    def _error(
        *,
        stage: AgentTraceMaintenanceStage,
        exception: Exception,
    ) -> AgentTraceMaintenanceError:
        """Convert an exception into a structured error."""

        message = str(exception).strip()

        if not message:
            message = "Maintenance stage failed."

        return AgentTraceMaintenanceError(
            stage=stage,
            error_type=type(exception).__name__,
            message=message,
        )
