"""Build operational reports from trace maintenance results."""

from __future__ import annotations

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_report import (
    AgentTraceMaintenanceReport,
)


class AgentTraceMaintenanceReporter:
    """Convert maintenance results into readable reports."""

    def build(
        self,
        result: AgentTraceMaintenanceResult,
    ) -> AgentTraceMaintenanceReport:
        """Build one operational report."""

        archived_file_count = (
            len(result.archive.files)
            if result.archive is not None
            else 0
        )
        scanned_file_count = (
            result.retention.scanned_file_count
            if result.retention is not None
            else 0
        )
        deleted_file_count = (
            result.retention.deleted_file_count
            if result.retention is not None
            else 0
        )

        details: list[str] = []

        if result.archive is not None:
            if result.archive.archived:
                details.append(
                    "Archive stage completed and wrote "
                    f"{archived_file_count} file(s)."
                )
            else:
                details.append(
                    "Archive stage completed without writing "
                    "files because the policy skipped this trace."
                )

        if result.retention is not None:
            details.append(
                "Retention stage scanned "
                f"{scanned_file_count} file(s) and deleted "
                f"{deleted_file_count} file(s)."
            )

        details.extend(
            (
                f"{error.stage.value} stage failed with "
                f"{error.error_type}: {error.message}"
            )
            for error in result.errors
        )

        return AgentTraceMaintenanceReport(
            trace_id=result.trace_id,
            status=result.status,
            headline=self._headline(result.status),
            details=details,
            archived_file_count=archived_file_count,
            scanned_file_count=scanned_file_count,
            deleted_file_count=deleted_file_count,
            error_count=len(result.errors),
        )

    @staticmethod
    def _headline(
        status: AgentTraceMaintenanceStatus,
    ) -> str:
        """Return a concise status headline."""

        headlines = {
            AgentTraceMaintenanceStatus.SUCCESS: (
                "Trace maintenance completed successfully."
            ),
            AgentTraceMaintenanceStatus.PARTIAL_SUCCESS: (
                "Trace maintenance completed with "
                "a stage failure."
            ),
            AgentTraceMaintenanceStatus.FAILED: (
                "Trace maintenance failed."
            ),
        }

        return headlines[status]
