"""Evaluate operational alerts for trace maintenance."""

from __future__ import annotations

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStage,
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)


class AgentTraceMaintenanceAlertEvaluator:
    """Determine whether a maintenance result needs alerting."""

    def evaluate(
        self,
        result: AgentTraceMaintenanceResult,
    ) -> AgentTraceMaintenanceAlert:
        """Evaluate one maintenance result."""

        if result.status is AgentTraceMaintenanceStatus.SUCCESS:
            return AgentTraceMaintenanceAlert(
                trace_id=result.trace_id,
                required=False,
                severity=(
                    AgentTraceMaintenanceAlertSeverity.NONE
                ),
                codes=[],
                message=(
                    "Trace maintenance completed without "
                    "operational errors."
                ),
            )

        codes = self._codes(result)

        if (
            result.status
            is AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
        ):
            severity = (
                AgentTraceMaintenanceAlertSeverity.WARNING
            )
            message = (
                "Trace maintenance partially succeeded; "
                "one stage requires attention."
            )
        else:
            severity = (
                AgentTraceMaintenanceAlertSeverity.CRITICAL
            )
            message = (
                "Trace maintenance failed in all stages."
            )

        return AgentTraceMaintenanceAlert(
            trace_id=result.trace_id,
            required=True,
            severity=severity,
            codes=codes,
            message=message,
        )

    @staticmethod
    def _codes(
        result: AgentTraceMaintenanceResult,
    ) -> list[AgentTraceMaintenanceAlertCode]:
        """Return ordered alert codes from stage failures."""

        stages = {
            error.stage
            for error in result.errors
        }

        if stages == {
            AgentTraceMaintenanceStage.ARCHIVE,
            AgentTraceMaintenanceStage.RETENTION,
        }:
            return [
                (
                    AgentTraceMaintenanceAlertCode
                    .MULTIPLE_STAGES_FAILED
                ),
                (
                    AgentTraceMaintenanceAlertCode
                    .ARCHIVE_STAGE_FAILED
                ),
                (
                    AgentTraceMaintenanceAlertCode
                    .RETENTION_STAGE_FAILED
                ),
            ]

        codes: list[
            AgentTraceMaintenanceAlertCode
        ] = []

        if AgentTraceMaintenanceStage.ARCHIVE in stages:
            codes.append(
                AgentTraceMaintenanceAlertCode
                .ARCHIVE_STAGE_FAILED
            )

        if AgentTraceMaintenanceStage.RETENTION in stages:
            codes.append(
                AgentTraceMaintenanceAlertCode
                .RETENTION_STAGE_FAILED
            )

        return codes
