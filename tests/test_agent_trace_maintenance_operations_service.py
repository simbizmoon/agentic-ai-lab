"""Tests for trace maintenance operations facade."""

import os
from datetime import timedelta
from pathlib import Path

import pytest

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlertSeverity,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)
from tests.test_agent_trace_maintenance_service import (
    NOW,
    maintenance_service,
)


def test_operations_service_returns_success_views(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceOperationsService(
        maintenance_service=maintenance_service(
            tmp_path,
            retention_policy=(
                AgentTraceRetentionPolicy(
                    maximum_file_count=10
                )
            ),
        )
    ).run("trace-001")

    assert result.maintenance.status is (
        AgentTraceMaintenanceStatus.SUCCESS
    )
    assert result.report.status is (
        AgentTraceMaintenanceStatus.SUCCESS
    )
    assert result.alert.required is False
    assert result.alert.severity is (
        AgentTraceMaintenanceAlertSeverity.NONE
    )
    assert result.report.archived_file_count == 2


def test_operations_report_includes_retention_counts(
    tmp_path: Path,
) -> None:
    old_file = tmp_path / "old.json"
    old_file.write_text(
        "{}",
        encoding="utf-8",
    )

    old_timestamp = (
        NOW - timedelta(days=100)
    ).timestamp()

    os.utime(
        old_file,
        (old_timestamp, old_timestamp),
    )

    result = AgentTraceMaintenanceOperationsService(
        maintenance_service=maintenance_service(
            tmp_path,
            retention_policy=(
                AgentTraceRetentionPolicy(
                    maximum_age_days=30
                )
            ),
        )
    ).run("trace-001")

    assert result.report.scanned_file_count == 3
    assert result.report.deleted_file_count == 1
    assert any(
        "deleted 1 file(s)"
        in detail
        for detail in result.report.details
    )


def test_operations_service_rejects_blank_trace_id(
    tmp_path: Path,
) -> None:
    service = AgentTraceMaintenanceOperationsService(
        maintenance_service=maintenance_service(
            tmp_path,
            retention_policy=(
                AgentTraceRetentionPolicy(
                    maximum_file_count=10
                )
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="trace_id must not be blank",
    ):
        service.run(" ")
