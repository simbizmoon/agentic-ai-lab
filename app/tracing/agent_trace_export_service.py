"""Facade for exporting recorded planning-agent traces."""

from __future__ import annotations

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
    AgentTraceExportResult,
)
from app.tracing.agent_trace_exporter import (
    AgentTraceExporter,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceReadService,
)


class AgentTraceExportService:
    """Read and export one recorded agent trace."""

    def __init__(
        self,
        *,
        read_service: AgentTraceReadService,
        exporter: AgentTraceExporter | None = None,
    ) -> None:
        self._read_service = read_service
        self._exporter = exporter or AgentTraceExporter()

    @property
    def read_service(self) -> AgentTraceReadService:
        """Return the configured trace read service."""

        return self._read_service

    @property
    def exporter(self) -> AgentTraceExporter:
        """Return the configured trace exporter."""

        return self._exporter

    def export(
        self,
        *,
        trace_id: str,
        format: AgentTraceExportFormat,
    ) -> AgentTraceExportResult:
        """Export one recorded trace."""

        timeline = self.read_service.timeline(trace_id)
        summary = self.read_service.summary(trace_id)

        return self.exporter.export(
            timeline=timeline,
            summary=summary,
            format=format,
        )
