"""Tests for partial and failed trace maintenance."""

from pathlib import Path

from app.schemas.agent_trace_maintenance import (
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
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)


class SuccessfulArchiveService:
    """Return one successful archive-stage result."""

    def archive(
        self,
        trace_id: str,
    ) -> AgentTracePolicyArchiveResult:
        return AgentTracePolicyArchiveResult(
            trace_id=trace_id,
            outcome=AgentTraceOutcome.INCOMPLETE,
            archived=False,
            files=[],
            reason="Archiving skipped by policy.",
        )


class FailingArchiveService:
    """Raise an archive-stage failure."""

    def archive(
        self,
        trace_id: str,
    ) -> AgentTracePolicyArchiveResult:
        raise RuntimeError(
            f"archive failed for {trace_id}"
        )


class SuccessfulRetentionService:
    """Return one successful retention-stage result."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory.resolve()

    def apply(
        self,
        policy: AgentTraceRetentionPolicy,
    ) -> AgentTraceRetentionResult:
        return AgentTraceRetentionResult(
            output_directory=self._directory,
            scanned_file_count=0,
            eligible_file_count=0,
            deleted_file_count=0,
            retained_file_count=0,
            dry_run=policy.dry_run,
            eligible_paths=[],
            deleted_paths=[],
        )


class FailingRetentionService:
    """Raise a retention-stage failure."""

    def apply(
        self,
        policy: AgentTraceRetentionPolicy,
    ) -> AgentTraceRetentionResult:
        raise OSError(
            f"retention failed: {policy.maximum_file_count}"
        )


def policy() -> AgentTraceRetentionPolicy:
    """Return one valid retention policy."""

    return AgentTraceRetentionPolicy(
        maximum_file_count=10
    )


def test_archive_success_retention_failure() -> None:
    result = AgentTraceMaintenanceService(
        archive_service=SuccessfulArchiveService(),
        retention_service=FailingRetentionService(),
        retention_policy=policy(),
    ).maintain("trace-001")

    assert result.status is (
        AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
    )
    assert result.archive is not None
    assert result.retention is None
    assert result.errors[0].stage is (
        AgentTraceMaintenanceStage.RETENTION
    )
    assert result.errors[0].error_type == "OSError"


def test_archive_failure_retention_success(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceService(
        archive_service=FailingArchiveService(),
        retention_service=SuccessfulRetentionService(
            tmp_path
        ),
        retention_policy=policy(),
    ).maintain("trace-001")

    assert result.status is (
        AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
    )
    assert result.archive is None
    assert result.retention is not None
    assert result.errors[0].stage is (
        AgentTraceMaintenanceStage.ARCHIVE
    )


def test_both_stages_fail() -> None:
    result = AgentTraceMaintenanceService(
        archive_service=FailingArchiveService(),
        retention_service=FailingRetentionService(),
        retention_policy=policy(),
    ).maintain("trace-001")

    assert result.status is (
        AgentTraceMaintenanceStatus.FAILED
    )
    assert result.archive is None
    assert result.retention is None
    assert [
        error.stage
        for error in result.errors
    ] == [
        AgentTraceMaintenanceStage.ARCHIVE,
        AgentTraceMaintenanceStage.RETENTION,
    ]


def test_blank_exception_message_gets_fallback() -> None:
    class BlankFailingArchiveService:
        def archive(
            self,
            trace_id: str,
        ) -> AgentTracePolicyArchiveResult:
            raise RuntimeError

    result = AgentTraceMaintenanceService(
        archive_service=BlankFailingArchiveService(),
        retention_service=FailingRetentionService(),
        retention_policy=policy(),
    ).maintain("trace-001")

    assert result.errors[0].message == (
        "Maintenance stage failed."
    )
