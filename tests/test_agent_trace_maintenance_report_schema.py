"""Tests for agent trace maintenance reports."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_report import (
    AgentTraceMaintenanceReport,
)


def test_report_accepts_valid_values() -> None:
    report = AgentTraceMaintenanceReport(
        trace_id="trace-001",
        status=AgentTraceMaintenanceStatus.SUCCESS,
        headline="Maintenance completed.",
        details=["Archive completed."],
        archived_file_count=2,
        scanned_file_count=5,
        deleted_file_count=1,
        error_count=0,
    )

    assert report.archived_file_count == 2


def test_report_rejects_blank_detail() -> None:
    with pytest.raises(
        ValidationError,
        match="details must not be blank",
    ):
        AgentTraceMaintenanceReport(
            trace_id="trace-001",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            headline="Maintenance completed.",
            details=[" "],
            archived_file_count=0,
            scanned_file_count=0,
            deleted_file_count=0,
            error_count=0,
        )


def test_report_rejects_blank_headline() -> None:
    with pytest.raises(
        ValidationError,
        match="headline must not be blank",
    ):
        AgentTraceMaintenanceReport(
            trace_id="trace-001",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            headline=" ",
            details=["Maintenance completed."],
            archived_file_count=0,
            scanned_file_count=0,
            deleted_file_count=0,
            error_count=0,
        )
