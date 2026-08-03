"""Tests for agent trace retention schemas."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
    AgentTraceRetentionResult,
)


def test_policy_accepts_age_constraint() -> None:
    policy = AgentTraceRetentionPolicy(
        maximum_age_days=30
    )

    assert policy.maximum_age_days == 30
    assert policy.maximum_file_count is None


def test_policy_accepts_count_constraint() -> None:
    policy = AgentTraceRetentionPolicy(
        maximum_file_count=100
    )

    assert policy.maximum_file_count == 100


def test_policy_requires_constraint() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one constraint",
    ):
        AgentTraceRetentionPolicy()


def test_policy_rejects_zero_age() -> None:
    with pytest.raises(ValidationError):
        AgentTraceRetentionPolicy(
            maximum_age_days=0
        )


def test_result_accepts_consistent_counts(
    tmp_path: Path,
) -> None:
    first = (tmp_path / "first.json").resolve()

    result = AgentTraceRetentionResult(
        output_directory=tmp_path.resolve(),
        scanned_file_count=2,
        eligible_file_count=1,
        deleted_file_count=1,
        retained_file_count=1,
        dry_run=False,
        eligible_paths=[first],
        deleted_paths=[first],
    )

    assert result.deleted_file_count == 1


def test_dry_run_rejects_deleted_paths(
    tmp_path: Path,
) -> None:
    target = (tmp_path / "trace.json").resolve()

    with pytest.raises(
        ValidationError,
        match="dry-run result",
    ):
        AgentTraceRetentionResult(
            output_directory=tmp_path.resolve(),
            scanned_file_count=1,
            eligible_file_count=1,
            deleted_file_count=1,
            retained_file_count=0,
            dry_run=True,
            eligible_paths=[target],
            deleted_paths=[target],
        )
