"""Tests for deterministic timeout and cancellation control."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.guardrails.execution_control import (
    CancellationMode,
    CancellationRequest,
    ExecutionControlDecisionType,
    ExecutionControlReason,
    ExecutionLifecycleStatus,
    ExecutionRuntimeSnapshot,
)
from app.guardrails.execution_control_evaluator import (
    ExecutionControlEvaluator,
)
from app.guardrails.execution_control_evaluator_error import (
    ExecutionControlEvaluatorError,
)
from app.guardrails.execution_timeout_policy import (
    ExecutionSubjectType,
    TimeoutPolicy,
    default_agent_timeout_policy,
)

BASE_TIME = datetime(
    2026,
    8,
    4,
    17,
    0,
    tzinfo=UTC,
)


def policy(
    *,
    soft_timeout_seconds: float | None = 10.0,
    hard_timeout_seconds: float | None = 20.0,
    cancellation_grace_period_seconds: float = 5.0,
    warn_on_soft_timeout: bool = True,
    cancel_on_hard_timeout: bool = True,
) -> TimeoutPolicy:
    """Return one test timeout policy."""

    return TimeoutPolicy(
        policy_id="timeout-policy-001",
        name="Test timeout policy",
        description="Control test execution duration.",
        version="1.0.0",
        subject_type=ExecutionSubjectType.AGENT,
        soft_timeout_seconds=soft_timeout_seconds,
        hard_timeout_seconds=hard_timeout_seconds,
        cancellation_grace_period_seconds=(
            cancellation_grace_period_seconds
        ),
        warn_on_soft_timeout=warn_on_soft_timeout,
        cancel_on_hard_timeout=cancel_on_hard_timeout,
    )


def cancellation_request(
    *,
    requested_at: datetime = BASE_TIME,
    mode: CancellationMode = CancellationMode.GRACEFUL,
) -> CancellationRequest:
    """Return one cancellation request."""

    return CancellationRequest(
        cancellation_id="cancel-001",
        requested_at=requested_at,
        requested_by="user-001",
        reason="The user cancelled the execution.",
        mode=mode,
    )


def snapshot(
    *,
    status: ExecutionLifecycleStatus = (
        ExecutionLifecycleStatus.RUNNING
    ),
    created_at: datetime = BASE_TIME,
    started_at: datetime | None = BASE_TIME,
    finished_at: datetime | None = None,
    deadline_at: datetime | None = None,
    cancellation: CancellationRequest | None = None,
    subject_type: ExecutionSubjectType = (
        ExecutionSubjectType.AGENT
    ),
) -> ExecutionRuntimeSnapshot:
    """Return one execution runtime snapshot."""

    return ExecutionRuntimeSnapshot(
        execution_id="execution-001",
        subject_id="agent-001",
        subject_type=subject_type,
        status=status,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        deadline_at=deadline_at,
        cancellation_request=cancellation,
    )


def evaluator(
    timeout_policy: TimeoutPolicy | None = None,
) -> ExecutionControlEvaluator:
    """Return one deterministic control evaluator."""

    return ExecutionControlEvaluator(
        policy=timeout_policy or policy(),
        decision_id_factory=(
            lambda: "control-decision-001"
        ),
    )


def test_execution_within_limits_continues() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(),
        now=BASE_TIME + timedelta(seconds=5),
    )

    assert value.decision is (
        ExecutionControlDecisionType.CONTINUE
    )
    assert value.reason is (
        ExecutionControlReason.WITHIN_LIMITS
    )
    assert value.should_stop is False
    assert value.elapsed_seconds == pytest.approx(5.0)
    assert value.remaining_soft_seconds == pytest.approx(5.0)
    assert value.remaining_hard_seconds == pytest.approx(15.0)


def test_soft_timeout_warns() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(),
        now=BASE_TIME + timedelta(seconds=10),
    )

    assert value.decision is ExecutionControlDecisionType.WARN
    assert value.reason is (
        ExecutionControlReason.SOFT_TIMEOUT_EXCEEDED
    )
    assert value.should_stop is False


def test_hard_timeout_stops_execution() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(),
        now=BASE_TIME + timedelta(seconds=20),
    )

    assert value.decision is (
        ExecutionControlDecisionType.TIMEOUT
    )
    assert value.reason is (
        ExecutionControlReason.HARD_TIMEOUT_EXCEEDED
    )
    assert value.should_stop is True


def test_absolute_deadline_takes_priority() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(
            deadline_at=BASE_TIME + timedelta(seconds=8)
        ),
        now=BASE_TIME + timedelta(seconds=8),
    )

    assert value.reason is (
        ExecutionControlReason.DEADLINE_EXCEEDED
    )
    assert value.should_stop is True


def test_graceful_cancellation_requests_shutdown() -> None:
    request = cancellation_request(
        requested_at=BASE_TIME + timedelta(seconds=3)
    )

    value = evaluator().evaluate(
        snapshot=snapshot(cancellation=request),
        now=BASE_TIME + timedelta(seconds=5),
    )

    assert value.decision is (
        ExecutionControlDecisionType.REQUEST_CANCELLATION
    )
    assert value.reason is (
        ExecutionControlReason
        .GRACEFUL_CANCELLATION_REQUESTED
    )
    assert value.should_stop is False
    assert (
        value.cancellation_grace_remaining_seconds
        == pytest.approx(3.0)
    )


def test_grace_period_expiry_forces_cancellation() -> None:
    request = cancellation_request(
        requested_at=BASE_TIME + timedelta(seconds=3)
    )

    value = evaluator().evaluate(
        snapshot=snapshot(cancellation=request),
        now=BASE_TIME + timedelta(seconds=8),
    )

    assert value.decision is (
        ExecutionControlDecisionType.FORCE_CANCEL
    )
    assert value.reason is (
        ExecutionControlReason
        .CANCELLATION_GRACE_PERIOD_EXCEEDED
    )
    assert value.should_stop is True


def test_force_cancellation_is_immediate() -> None:
    request = cancellation_request(
        requested_at=BASE_TIME + timedelta(seconds=3),
        mode=CancellationMode.FORCE,
    )

    value = evaluator().evaluate(
        snapshot=snapshot(cancellation=request),
        now=BASE_TIME + timedelta(seconds=4),
    )

    assert value.decision is (
        ExecutionControlDecisionType.FORCE_CANCEL
    )
    assert value.reason is (
        ExecutionControlReason
        .FORCE_CANCELLATION_REQUESTED
    )


def test_terminal_execution_is_not_reprocessed() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(
            status=ExecutionLifecycleStatus.COMPLETED,
            finished_at=BASE_TIME + timedelta(seconds=4),
        ),
        now=BASE_TIME + timedelta(seconds=30),
    )

    assert value.decision is (
        ExecutionControlDecisionType.TERMINAL
    )
    assert value.reason is (
        ExecutionControlReason.EXECUTION_ALREADY_TERMINAL
    )
    assert value.elapsed_seconds == pytest.approx(4.0)


def test_created_execution_uses_created_at() -> None:
    value = evaluator().evaluate(
        snapshot=snapshot(
            status=ExecutionLifecycleStatus.CREATED,
            started_at=None,
        ),
        now=BASE_TIME + timedelta(seconds=5),
    )

    assert value.elapsed_seconds == pytest.approx(5.0)


def test_disabled_soft_warning_continues() -> None:
    timeout_policy = policy(
        warn_on_soft_timeout=False
    )

    value = evaluator(timeout_policy).evaluate(
        snapshot=snapshot(),
        now=BASE_TIME + timedelta(seconds=12),
    )

    assert value.decision is (
        ExecutionControlDecisionType.CONTINUE
    )


def test_disabled_hard_cancellation_warns_after_soft_limit() -> None:
    timeout_policy = policy(
        cancel_on_hard_timeout=False
    )

    value = evaluator(timeout_policy).evaluate(
        snapshot=snapshot(),
        now=BASE_TIME + timedelta(seconds=25),
    )

    assert value.decision is ExecutionControlDecisionType.WARN
    assert value.should_stop is False


def test_subject_type_mismatch_fails() -> None:
    with pytest.raises(
        ExecutionControlEvaluatorError,
        match=(
            "snapshot subject_type must match timeout policy"
        ),
    ):
        evaluator().evaluate(
            snapshot=snapshot(
                subject_type=ExecutionSubjectType.TOOL
            ),
            now=BASE_TIME,
        )


def test_naive_now_fails() -> None:
    with pytest.raises(
        ExecutionControlEvaluatorError,
        match="now must be timezone-aware",
    ):
        evaluator().evaluate(
            snapshot=snapshot(),
            now=datetime(2026, 8, 4, 17, 0),  # noqa: DTZ001
        )


def test_now_before_start_fails() -> None:
    with pytest.raises(
        ExecutionControlEvaluatorError,
        match="now must not precede started_at",
    ):
        evaluator().evaluate(
            snapshot=snapshot(),
            now=BASE_TIME - timedelta(seconds=1),
        )


def test_snapshot_rejects_terminal_without_finished_at() -> None:
    with pytest.raises(
        ValidationError,
        match="terminal execution requires finished_at",
    ):
        snapshot(
            status=ExecutionLifecycleStatus.COMPLETED,
        )


def test_snapshot_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        snapshot(
            created_at=datetime(2026, 8, 4, 17, 0),  # noqa: DTZ001
            started_at=None,
        )


def test_policy_rejects_invalid_timeout_order() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "soft_timeout_seconds must be less than "
            "hard_timeout_seconds"
        ),
    ):
        policy(
            soft_timeout_seconds=20.0,
            hard_timeout_seconds=10.0,
        )


def test_policy_requires_timeout_limit() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "timeout policy requires a soft or hard timeout"
        ),
    ):
        policy(
            soft_timeout_seconds=None,
            hard_timeout_seconds=None,
            warn_on_soft_timeout=False,
            cancel_on_hard_timeout=False,
        )


def test_default_agent_policy_is_configured() -> None:
    value = default_agent_timeout_policy()

    assert value.subject_type is ExecutionSubjectType.AGENT
    assert value.soft_timeout_seconds == pytest.approx(120.0)
    assert value.hard_timeout_seconds == pytest.approx(300.0)


def test_blank_decision_id_fails() -> None:
    value = ExecutionControlEvaluator(
        policy=policy(),
        decision_id_factory=lambda: " ",
    )

    with pytest.raises(
        ExecutionControlEvaluatorError,
        match="decision_id factory returned blank value",
    ):
        value.evaluate(
            snapshot=snapshot(),
            now=BASE_TIME,
        )
