"""Tests for trace maintenance alert schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)


def test_non_required_alert_accepts_none_severity() -> None:
    alert = AgentTraceMaintenanceAlert(
        trace_id="trace-001",
        required=False,
        severity=AgentTraceMaintenanceAlertSeverity.NONE,
        codes=[],
        message="No alert required.",
    )

    assert alert.required is False


def test_required_alert_requires_codes() -> None:
    with pytest.raises(
        ValidationError,
        match="must contain codes",
    ):
        AgentTraceMaintenanceAlert(
            trace_id="trace-001",
            required=True,
            severity=(
                AgentTraceMaintenanceAlertSeverity.WARNING
            ),
            codes=[],
            message="Attention required.",
        )


def test_non_required_alert_rejects_codes() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain codes",
    ):
        AgentTraceMaintenanceAlert(
            trace_id="trace-001",
            required=False,
            severity=(
                AgentTraceMaintenanceAlertSeverity.NONE
            ),
            codes=[
                (
                    AgentTraceMaintenanceAlertCode
                    .ARCHIVE_STAGE_FAILED
                )
            ],
            message="No alert required.",
        )


def test_alert_rejects_duplicate_codes() -> None:
    with pytest.raises(
        ValidationError,
        match="codes must be unique",
    ):
        AgentTraceMaintenanceAlert(
            trace_id="trace-001",
            required=True,
            severity=(
                AgentTraceMaintenanceAlertSeverity.CRITICAL
            ),
            codes=[
                (
                    AgentTraceMaintenanceAlertCode
                    .ARCHIVE_STAGE_FAILED
                ),
                (
                    AgentTraceMaintenanceAlertCode
                    .ARCHIVE_STAGE_FAILED
                ),
            ],
            message="Attention required.",
        )
