"""Deterministic timeout and cancellation evaluation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from app.guardrails.execution_control import (
    CancellationMode,
    ExecutionControlDecision,
    ExecutionControlDecisionType,
    ExecutionControlReason,
    ExecutionLifecycleStatus,
    ExecutionRuntimeSnapshot,
)
from app.guardrails.execution_control_evaluator_error import (
    ExecutionControlEvaluatorError,
)
from app.guardrails.execution_timeout_policy import (
    TimeoutPolicy,
)


class ExecutionControlEvaluator:
    """Evaluate whether an execution may continue."""

    def __init__(
        self,
        *,
        policy: TimeoutPolicy,
        decision_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._policy = policy
        self._decision_id_factory = (
            decision_id_factory
            or (lambda: f"execution-control-{uuid4()}")
        )

    def evaluate(
        self,
        *,
        snapshot: ExecutionRuntimeSnapshot,
        now: datetime,
    ) -> ExecutionControlDecision:
        """Evaluate timeout and cancellation state."""

        if now.tzinfo is None:
            raise ExecutionControlEvaluatorError(
                "now must be timezone-aware"
            )

        if snapshot.subject_type is not self._policy.subject_type:
            raise ExecutionControlEvaluatorError(
                "snapshot subject_type must match timeout policy"
            )

        terminal_statuses = {
            ExecutionLifecycleStatus.COMPLETED,
            ExecutionLifecycleStatus.FAILED,
            ExecutionLifecycleStatus.CANCELLED,
            ExecutionLifecycleStatus.TIMED_OUT,
        }

        if snapshot.status in terminal_statuses:
            return self._decision(
                snapshot=snapshot,
                now=now,
                decision=ExecutionControlDecisionType.TERMINAL,
                reason=(
                    ExecutionControlReason
                    .EXECUTION_ALREADY_TERMINAL
                ),
                should_stop=True,
            )

        if (
            snapshot.started_at is not None
            and now < snapshot.started_at
        ):
            raise ExecutionControlEvaluatorError(
                "now must not precede started_at"
            )

        cancellation = snapshot.cancellation_request

        if cancellation is not None:
            if now < cancellation.requested_at:
                raise ExecutionControlEvaluatorError(
                    "now must not precede cancellation request"
                )

            if cancellation.mode is CancellationMode.FORCE:
                return self._decision(
                    snapshot=snapshot,
                    now=now,
                    decision=(
                        ExecutionControlDecisionType.FORCE_CANCEL
                    ),
                    reason=(
                        ExecutionControlReason
                        .FORCE_CANCELLATION_REQUESTED
                    ),
                    should_stop=True,
                )

            grace_elapsed = (
                now - cancellation.requested_at
            ).total_seconds()
            grace_limit = (
                self._policy
                .cancellation_grace_period_seconds
            )

            if grace_elapsed >= grace_limit:
                return self._decision(
                    snapshot=snapshot,
                    now=now,
                    decision=(
                        ExecutionControlDecisionType.FORCE_CANCEL
                    ),
                    reason=(
                        ExecutionControlReason
                        .CANCELLATION_GRACE_PERIOD_EXCEEDED
                    ),
                    should_stop=True,
                )

            return self._decision(
                snapshot=snapshot,
                now=now,
                decision=(
                    ExecutionControlDecisionType
                    .REQUEST_CANCELLATION
                ),
                reason=(
                    ExecutionControlReason
                    .GRACEFUL_CANCELLATION_REQUESTED
                ),
                should_stop=False,
            )

        if (
            snapshot.deadline_at is not None
            and now >= snapshot.deadline_at
        ):
            return self._decision(
                snapshot=snapshot,
                now=now,
                decision=ExecutionControlDecisionType.TIMEOUT,
                reason=ExecutionControlReason.DEADLINE_EXCEEDED,
                should_stop=True,
            )

        elapsed = self._elapsed_seconds(
            snapshot=snapshot,
            now=now,
        )

        if (
            self._policy.hard_timeout_seconds is not None
            and elapsed
            >= self._policy.hard_timeout_seconds
            and self._policy.cancel_on_hard_timeout
        ):
            return self._decision(
                snapshot=snapshot,
                now=now,
                decision=ExecutionControlDecisionType.TIMEOUT,
                reason=(
                    ExecutionControlReason
                    .HARD_TIMEOUT_EXCEEDED
                ),
                should_stop=True,
            )

        if (
            self._policy.soft_timeout_seconds is not None
            and elapsed
            >= self._policy.soft_timeout_seconds
            and self._policy.warn_on_soft_timeout
        ):
            return self._decision(
                snapshot=snapshot,
                now=now,
                decision=ExecutionControlDecisionType.WARN,
                reason=(
                    ExecutionControlReason
                    .SOFT_TIMEOUT_EXCEEDED
                ),
                should_stop=False,
            )

        return self._decision(
            snapshot=snapshot,
            now=now,
            decision=ExecutionControlDecisionType.CONTINUE,
            reason=ExecutionControlReason.WITHIN_LIMITS,
            should_stop=False,
        )

    def _decision(
        self,
        *,
        snapshot: ExecutionRuntimeSnapshot,
        now: datetime,
        decision: ExecutionControlDecisionType,
        reason: ExecutionControlReason,
        should_stop: bool,
    ) -> ExecutionControlDecision:
        """Build one complete execution-control decision."""

        elapsed = self._elapsed_seconds(
            snapshot=snapshot,
            now=now,
        )

        return ExecutionControlDecision(
            decision_id=self._new_identifier(),
            policy_id=self._policy.policy_id,
            execution_id=snapshot.execution_id,
            decision=decision,
            reason=reason,
            elapsed_seconds=elapsed,
            remaining_soft_seconds=self._remaining(
                limit=self._policy.soft_timeout_seconds,
                elapsed=elapsed,
            ),
            remaining_hard_seconds=self._remaining(
                limit=self._policy.hard_timeout_seconds,
                elapsed=elapsed,
            ),
            remaining_deadline_seconds=(
                None
                if snapshot.deadline_at is None
                else (
                    snapshot.deadline_at - now
                ).total_seconds()
            ),
            cancellation_grace_remaining_seconds=(
                self._grace_remaining(
                    snapshot=snapshot,
                    now=now,
                )
            ),
            should_stop=should_stop,
            summary=(
                "Execution control completed with decision "
                f"{decision.value} because {reason.value}."
            ),
            metadata={
                "subject_id": snapshot.subject_id,
                "subject_type": snapshot.subject_type.value,
                "execution_status": snapshot.status.value,
            },
        )

    @staticmethod
    def _elapsed_seconds(
        *,
        snapshot: ExecutionRuntimeSnapshot,
        now: datetime,
    ) -> float:
        """Return nonnegative elapsed runtime."""

        start = snapshot.started_at or snapshot.created_at
        end = snapshot.finished_at or now

        return max(
            0.0,
            (end - start).total_seconds(),
        )

    @staticmethod
    def _remaining(
        *,
        limit: float | None,
        elapsed: float,
    ) -> float | None:
        """Return remaining duration for one timeout limit."""

        if limit is None:
            return None

        return limit - elapsed

    def _grace_remaining(
        self,
        *,
        snapshot: ExecutionRuntimeSnapshot,
        now: datetime,
    ) -> float | None:
        """Return remaining cancellation grace period."""

        cancellation = snapshot.cancellation_request

        if cancellation is None:
            return None

        elapsed = (
            now - cancellation.requested_at
        ).total_seconds()

        return (
            self._policy.cancellation_grace_period_seconds
            - elapsed
        )

    def _new_identifier(self) -> str:
        """Generate one nonblank decision identifier."""

        value = self._decision_id_factory()

        if not value.strip():
            raise ExecutionControlEvaluatorError(
                "decision_id factory returned blank value"
            )

        return value
