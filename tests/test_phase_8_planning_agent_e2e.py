"""Phase 8 end-to-end test for the planning agent."""

from __future__ import annotations

from pathlib import Path

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_archive_policy import (
    AgentTraceArchivePolicy,
)
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopStatus,
)
from app.schemas.tool_execution import ToolExecutionStatus
from app.tracing.agent_trace_archive_service import (
    AgentTraceArchiveService,
)
from app.tracing.agent_trace_export_service import (
    AgentTraceExportService,
)
from app.tracing.agent_trace_file_writer import (
    AgentTraceFileWriter,
)
from app.tracing.agent_trace_maintenance_notification_service import (
    AgentTraceMaintenanceNotificationService,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)
from app.tracing.agent_trace_policy_archive_service import (
    AgentTracePolicyArchiveService,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceReadService,
)
from app.tracing.agent_trace_retention_service import (
    AgentTraceRetentionService,
)
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)
from app.tracing.in_memory_agent_trace_alert_notifier import (
    InMemoryAgentTraceAlertNotifier,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)
from tests.test_in_memory_agent_trace_alert_notifier import (
    FixedNotificationIdGenerator,
)
from tests.test_planning_agent_loop import (
    SequencedPlannerClient,
    SequencedTool,
    build_loop,
    loop_request,
    planner_output,
)


def test_phase_8_complete_planning_agent_flow(
    tmp_path: Path,
) -> None:
    """Verify planning, replanning, tracing, and operations."""

    recorder = InMemoryTraceRecorder()
    trace_session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-phase-8",
    )

    loop = build_loop(
        planner_client=SequencedPlannerClient(
            outputs=[
                planner_output(
                    title="Initial failing plan"
                ),
                planner_output(
                    title="Replacement successful plan"
                ),
            ]
        ),
        tool=SequencedTool(
            statuses=[
                ToolExecutionStatus.FAILED,
                ToolExecutionStatus.SUCCEEDED,
            ]
        ),
    )

    loop_result = loop.run(
        loop_request(maximum_replans=1),
        trace_session=trace_session,
    )

    assert loop_result.status is (
        PlanningAgentLoopStatus.GOAL_ACHIEVED
    )
    assert loop_result.trace_id == "trace-phase-8"
    assert len(loop_result.attempts) == 2
    assert loop_result.attempts[0].attempt_number == 1
    assert loop_result.attempts[1].attempt_number == 2

    read_service = AgentTraceReadService(
        recorder=recorder
    )
    timeline = read_service.timeline(
        "trace-phase-8"
    )
    summary = read_service.summary(
        "trace-phase-8"
    )

    assert timeline.trace_id == "trace-phase-8"
    assert len(timeline.items) > 0
    assert summary.outcome is (
        AgentTraceOutcome.COMPLETED
    )
    assert summary.attempt_count == 2
    assert summary.replanning_count == 1
    assert summary.step_failed_count == 1
    assert summary.step_completed_count == 1
    assert summary.tool_failed_count == 1
    assert summary.tool_completed_count == 1

    export_service = AgentTraceExportService(
        read_service=read_service
    )
    file_writer = AgentTraceFileWriter(
        output_directory=tmp_path
    )
    archive_service = AgentTraceArchiveService(
        export_service=export_service,
        file_writer=file_writer,
    )
    policy_archive_service = (
        AgentTracePolicyArchiveService(
            read_service=read_service,
            archive_service=archive_service,
            policy=AgentTraceArchivePolicy(
                formats=[
                    AgentTraceExportFormat.JSON,
                    AgentTraceExportFormat.MARKDOWN,
                ],
                archive_completed=True,
                archive_failed=True,
                overwrite=False,
            ),
        )
    )

    maintenance_service = AgentTraceMaintenanceService(
        archive_service=policy_archive_service,
        retention_service=(
            AgentTraceRetentionService(
                output_directory=tmp_path
            )
        ),
        retention_policy=AgentTraceRetentionPolicy(
            maximum_file_count=10
        ),
    )

    notifier = InMemoryAgentTraceAlertNotifier(
        id_generator=FixedNotificationIdGenerator()
    )

    result = (
        AgentTraceMaintenanceNotificationService(
            operations_service=(
                AgentTraceMaintenanceOperationsService(
                    maintenance_service=maintenance_service
                )
            ),
            notifier=notifier,
            channel="memory",
            destination="operations",
            metadata={
                "phase": "8",
                "environment": "test",
            },
        )
        .run("trace-phase-8")
    )

    assert result.operations.maintenance.archive is not None
    assert result.operations.maintenance.retention is not None
    assert result.operations.maintenance.archive.archived is True

    archived_paths = {
        file.path
        for file in (
            result.operations
            .maintenance
            .archive
            .files
        )
    }

    assert archived_paths == {
        (tmp_path / "trace-phase-8.json").resolve(),
        (tmp_path / "trace-phase-8.md").resolve(),
    }

    assert all(
        path.exists()
        for path in archived_paths
    )

    assert (
        result.operations
        .maintenance
        .retention
        .scanned_file_count
        == 2
    )
    assert result.operations.alert.required is False
    assert result.notification.status is (
        AgentTraceAlertNotificationStatus.SKIPPED
    )
    assert result.notification.notification_id is None
    assert len(notifier.requests()) == 1
    assert len(notifier.results()) == 1
