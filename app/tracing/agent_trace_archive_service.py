"""Export and persist recorded planning-agent traces."""

from __future__ import annotations

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteRequest,
    AgentTraceFileWriteResult,
)
from app.tracing.agent_trace_export_service import (
    AgentTraceExportService,
)
from app.tracing.agent_trace_file_writer import (
    AgentTraceFileWriter,
)


class AgentTraceArchiveService:
    """Export one recorded trace and save it to disk."""

    def __init__(
        self,
        *,
        export_service: AgentTraceExportService,
        file_writer: AgentTraceFileWriter,
    ) -> None:
        self._export_service = export_service
        self._file_writer = file_writer

    @property
    def export_service(self) -> AgentTraceExportService:
        """Return the configured export service."""

        return self._export_service

    @property
    def file_writer(self) -> AgentTraceFileWriter:
        """Return the configured file writer."""

        return self._file_writer

    def archive(
        self,
        *,
        trace_id: str,
        format: AgentTraceExportFormat,
        request: AgentTraceFileWriteRequest | None = None,
    ) -> AgentTraceFileWriteResult:
        """Export and save one trace."""

        exported = self.export_service.export(
            trace_id=trace_id,
            format=format,
        )

        return self.file_writer.write(
            export=exported,
            request=request,
        )
