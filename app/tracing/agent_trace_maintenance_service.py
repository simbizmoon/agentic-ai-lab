"""Operational maintenance for archived agent traces."""

from __future__ import annotations

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
)
from app.tracing.agent_trace_policy_archive_service import (
    AgentTracePolicyArchiveService,
)
from app.tracing.agent_trace_retention_service import (
    AgentTraceRetentionService,
)


class AgentTraceMaintenanceService:
    """Archive one trace and then apply retention."""

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
        """Archive one trace and apply retention."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        archive_result = self.archive_service.archive(
            trace_id
        )

        retention_result = self.retention_service.apply(
            self.retention_policy
        )

        return AgentTraceMaintenanceResult(
            trace_id=trace_id,
            archive=archive_result,
            retention=retention_result,
        )
