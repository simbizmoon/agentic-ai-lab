"""Tests for agent trace archive policy schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_archive_policy import (
    AgentTraceArchivePolicy,
)
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)


def test_policy_accepts_multiple_formats() -> None:
    policy = AgentTraceArchivePolicy(
        formats=[
            AgentTraceExportFormat.JSON,
            AgentTraceExportFormat.MARKDOWN,
        ]
    )

    assert policy.archive_completed is True
    assert policy.archive_failed is True
    assert policy.archive_incomplete is False
    assert policy.overwrite is False


def test_policy_rejects_duplicate_formats() -> None:
    with pytest.raises(
        ValidationError,
        match="formats must be unique",
    ):
        AgentTraceArchivePolicy(
            formats=[
                AgentTraceExportFormat.JSON,
                AgentTraceExportFormat.JSON,
            ]
        )


def test_policy_requires_enabled_outcome() -> None:
    with pytest.raises(
        ValidationError,
        match="enable at least one outcome",
    ):
        AgentTraceArchivePolicy(
            formats=[AgentTraceExportFormat.JSON],
            archive_completed=False,
            archive_failed=False,
            archive_incomplete=False,
        )


def test_policy_requires_at_least_one_format() -> None:
    with pytest.raises(ValidationError):
        AgentTraceArchivePolicy(formats=[])
