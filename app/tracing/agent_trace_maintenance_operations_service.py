"""Operational facade for agent trace maintenance."""

from __future__ import annotations

from app.schemas.agent_trace_maintenance_operations import (
    AgentTraceMaintenanceOperationsResult,
)
from app.tracing.agent_trace_maintenance_alert_evaluator import (
    AgentTraceMaintenanceAlertEvaluator,
)
from app.tracing.agent_trace_maintenance_reporter import (
    AgentTraceMaintenanceReporter,
)
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)


class AgentTraceMaintenanceOperationsService:
    """Run maintenance and build operational views."""

    def __init__(
        self,
        *,
        maintenance_service: AgentTraceMaintenanceService,
        reporter: AgentTraceMaintenanceReporter | None = None,
        alert_evaluator: (
            AgentTraceMaintenanceAlertEvaluator | None
        ) = None,
    ) -> None:
        self._maintenance_service = maintenance_service
        self._reporter = (
            reporter or AgentTraceMaintenanceReporter()
        )
        self._alert_evaluator = (
            alert_evaluator
            or AgentTraceMaintenanceAlertEvaluator()
        )

    @property
    def maintenance_service(
        self,
    ) -> AgentTraceMaintenanceService:
        """Return the configured maintenance service."""

        return self._maintenance_service

    @property
    def reporter(
        self,
    ) -> AgentTraceMaintenanceReporter:
        """Return the configured maintenance reporter."""

        return self._reporter

    @property
    def alert_evaluator(
        self,
    ) -> AgentTraceMaintenanceAlertEvaluator:
        """Return the configured alert evaluator."""

        return self._alert_evaluator

    def run(
        self,
        trace_id: str,
    ) -> AgentTraceMaintenanceOperationsResult:
        """Run trace maintenance and build operations views."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        maintenance = self.maintenance_service.maintain(
            trace_id
        )
        report = self.reporter.build(maintenance)
        alert = self.alert_evaluator.evaluate(
            maintenance
        )

        return AgentTraceMaintenanceOperationsResult(
            trace_id=trace_id,
            maintenance=maintenance,
            report=report,
            alert=alert,
        )
