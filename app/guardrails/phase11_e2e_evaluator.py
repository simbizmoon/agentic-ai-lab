"""End-to-end evaluation of Phase 11 reliability components."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import uuid4

from app.guardrails.failure_recovery import (
    FailureRecoveryContext,
)
from app.guardrails.failure_recovery_evaluator import (
    FailureRecoveryEvaluator,
)
from app.guardrails.input_guardrail_evaluator import (
    InputGuardrailEvaluator,
)
from app.guardrails.input_guardrail_snapshot import (
    InputGuardrailSnapshot,
)
from app.guardrails.phase11_e2e_evaluator_error import (
    Phase11E2EEvaluatorError,
)
from app.guardrails.phase11_e2e_result import (
    Phase11E2EResult,
)
from app.guardrails.reliability_metrics import (
    ReliabilityExecutionRecord,
)
from app.guardrails.reliability_metrics_calculator import (
    ReliabilityMetricsCalculator,
)
from app.guardrails.retry_decision import (
    RetryDecision,
    RetryFailureContext,
)
from app.guardrails.retry_policy_evaluator import (
    RetryPolicyEvaluator,
)
from app.guardrails.tool_permission_guardrail_evaluator import (
    ToolPermissionGuardrailEvaluator,
)
from app.guardrails.tool_permission_guardrail_snapshot import (
    ToolPermissionGuardrailSnapshot,
)


class Phase11E2EEvaluator:
    """Connect Phase 11 guardrails and reliability evaluation."""

    def __init__(
        self,
        *,
        input_guardrail_evaluator: InputGuardrailEvaluator,
        tool_guardrail_evaluator: (
            ToolPermissionGuardrailEvaluator
        ),
        retry_policy_evaluator: RetryPolicyEvaluator,
        failure_recovery_evaluator: FailureRecoveryEvaluator,
        reliability_metrics_calculator: (
            ReliabilityMetricsCalculator
        ),
        evaluation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._input_guardrail_evaluator = (
            input_guardrail_evaluator
        )
        self._tool_guardrail_evaluator = (
            tool_guardrail_evaluator
        )
        self._retry_policy_evaluator = (
            retry_policy_evaluator
        )
        self._failure_recovery_evaluator = (
            failure_recovery_evaluator
        )
        self._reliability_metrics_calculator = (
            reliability_metrics_calculator
        )
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"phase11-e2e-{uuid4()}")
        )

    def evaluate(
        self,
        *,
        input_snapshot: InputGuardrailSnapshot,
        denied_tool_snapshot: (
            ToolPermissionGuardrailSnapshot
        ),
        allowed_tool_snapshot: (
            ToolPermissionGuardrailSnapshot
        ),
        retry_failures: Sequence[RetryFailureContext],
        recovery_context: FailureRecoveryContext,
        execution_records: Sequence[
            ReliabilityExecutionRecord
        ],
    ) -> Phase11E2EResult:
        """Execute the complete Phase 11 reliability scenario."""

        input_result = self._input_guardrail_evaluator.evaluate(
            input_snapshot
        )

        if not input_result.allowed:
            raise Phase11E2EEvaluatorError(
                "input guardrail blocked the E2E scenario"
            )

        denied_tool_result = (
            self._tool_guardrail_evaluator.evaluate(
                denied_tool_snapshot
            )
        )

        if denied_tool_result.allowed:
            raise Phase11E2EEvaluatorError(
                "denied tool call was unexpectedly allowed"
            )

        allowed_tool_result = (
            self._tool_guardrail_evaluator.evaluate(
                allowed_tool_snapshot
            )
        )

        if not allowed_tool_result.allowed:
            raise Phase11E2EEvaluatorError(
                "allowed tool call was unexpectedly blocked"
            )

        if not retry_failures:
            raise Phase11E2EEvaluatorError(
                "E2E scenario requires retry failures"
            )

        retry_decisions: list[RetryDecision] = []

        for failure in retry_failures:
            retry_decisions.append(
                self._retry_policy_evaluator.evaluate(
                    failure
                )
            )

        recovery_decision = (
            self._failure_recovery_evaluator.evaluate(
                recovery_context
            )
        )

        reliability_metrics = (
            self._reliability_metrics_calculator.calculate(
                execution_records
            )
        )

        evaluation_id = self._evaluation_id_factory()

        if not evaluation_id.strip():
            raise Phase11E2EEvaluatorError(
                "evaluation_id factory returned blank value"
            )

        return Phase11E2EResult(
            evaluation_id=evaluation_id,
            input_guardrail_result=input_result,
            denied_tool_guardrail_result=denied_tool_result,
            allowed_tool_guardrail_result=allowed_tool_result,
            retry_decisions=retry_decisions,
            recovery_decision=recovery_decision,
            reliability_metrics=reliability_metrics,
            completed=True,
            summary=(
                "Phase 11 E2E evaluation completed with "
                f"{len(retry_decisions)} retry decisions, "
                f"recovery strategy "
                f"{recovery_decision.strategy.value}, and "
                f"success rate "
                f"{reliability_metrics.success_rate:.4f}."
            ),
            metadata={
                "assignment_id": (
                    input_snapshot.assignment.assignment_id
                ),
                "request_id": (
                    input_snapshot.assignment.request_id
                ),
                "workspace_id": (
                    input_snapshot.assignment.workspace_id
                ),
            },
        )
