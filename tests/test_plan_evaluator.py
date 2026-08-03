"""Tests for deterministic evaluation of plan runs."""

from __future__ import annotations

from datetime import UTC, datetime

from app.planning.plan_evaluator import PlanEvaluator
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
)
from app.schemas.plan_execution import (
    PlanExecutionResult,
    PlanExecutionStatus,
)
from app.schemas.plan_run import (
    PlanRunResult,
    PlanRunStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleResult,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
    PlanStepExecutionStatus,
)
from app.schemas.plan_validation import (
    PlanValidationCode,
    PlanValidationIssue,
    PlanValidationResult,
    PlanValidationSeverity,
)

NOW = datetime(
    2026,
    8,
    3,
    20,
    0,
    tzinfo=UTC,
)


def step(
    *,
    step_id: str = "step-1",
    status: PlanStepStatus,
) -> PlanStep:
    """Return one plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        status=status,
        tool_name="python",
    )


def plan(
    *,
    status: PlanStatus,
    steps: list[PlanStep],
) -> Plan:
    """Return one structured plan."""

    return Plan(
        plan_id="plan-001",
        goal="Execute the complete plan.",
        status=status,
        steps=steps,
        created_at=NOW,
        updated_at=NOW,
    )


def validation(
    *,
    valid: bool = True,
) -> PlanValidationResult:
    """Return one validation result."""

    if valid:
        return PlanValidationResult(
            valid=True,
            issues=[],
            execution_order=["step-1"],
        )

    return PlanValidationResult(
        valid=False,
        issues=[
            PlanValidationIssue(
                code=(
                    PlanValidationCode
                    .CIRCULAR_DEPENDENCY
                ),
                severity=(
                    PlanValidationSeverity.ERROR
                ),
                message="The plan contains a cycle.",
            )
        ],
        execution_order=[],
    )


def schedule(
    *,
    selected: bool,
) -> PlanScheduleResult:
    """Return one schedule result."""

    return PlanScheduleResult(
        selected_step_ids=(
            ["step-1"] if selected else []
        ),
        ready_step_ids=(
            ["step-1"] if selected else []
        ),
        active_step_ids=[],
        reason=(
            PlanScheduleReason.STEPS_SELECTED
            if selected
            else PlanScheduleReason.NO_READY_STEPS
        ),
    )


def failed_cycle() -> PlanExecutionResult:
    """Return one failed execution cycle."""

    failed_plan = plan(
        status=PlanStatus.FAILED,
        steps=[
            step(
                status=PlanStepStatus.FAILED
            )
        ],
    )

    return PlanExecutionResult(
        plan=failed_plan,
        validation=validation(),
        schedule=schedule(selected=True),
        step_results=[
            PlanStepExecutionResult(
                step_id="step-1",
                tool_name="python",
                status=(
                    PlanStepExecutionStatus.FAILED
                ),
                error_message="Execution failed.",
            )
        ],
        status=PlanExecutionStatus.STEP_FAILED,
    )


def run_result(
    *,
    plan_value: Plan,
    status: PlanRunStatus,
    cycles: list[PlanExecutionResult] | None = None,
    validation_value: PlanValidationResult | None = None,
) -> PlanRunResult:
    """Return one plan-run result."""

    cycle_values = cycles or []
    executed_ids = [
        result.step_id
        for cycle in cycle_values
        for result in cycle.step_results
    ]

    return PlanRunResult(
        plan=plan_value,
        validation=(
            validation_value or validation()
        ),
        cycles=cycle_values,
        status=status,
        message="Run finished.",
        executed_step_ids=list(
            dict.fromkeys(executed_ids)
        ),
    )


def test_completed_plan_achieves_goal() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.COMPLETED,
                steps=[
                    step(
                        status=(
                            PlanStepStatus.COMPLETED
                        )
                    )
                ],
            ),
            status=PlanRunStatus.COMPLETED,
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.GOAL_ACHIEVED
    )
    assert result.codes == [
        PlanEvaluationCode.PLAN_COMPLETED
    ]


def test_failed_step_requires_replanning() -> None:
    cycle = failed_cycle()

    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=cycle.plan,
            status=PlanRunStatus.FAILED,
            cycles=[cycle],
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.REPLAN_REQUIRED
    )
    assert result.failed_step_ids == ["step-1"]
    assert result.replan_recommended is True


def test_blocked_plan_requires_replanning() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.IN_PROGRESS,
                steps=[
                    step(
                        status=PlanStepStatus.PENDING
                    )
                ],
            ),
            status=PlanRunStatus.BLOCKED,
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.REPLAN_REQUIRED
    )
    assert result.codes == [
        PlanEvaluationCode.NO_EXECUTABLE_STEP
    ]


def test_cycle_limit_requires_replanning() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.IN_PROGRESS,
                steps=[
                    step(
                        status=PlanStepStatus.READY
                    )
                ],
            ),
            status=(
                PlanRunStatus.CYCLE_LIMIT_REACHED
            ),
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.REPLAN_REQUIRED
    )
    assert result.codes == [
        PlanEvaluationCode.CYCLE_LIMIT_REACHED
    ]


def test_invalid_plan_requires_human_review() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.IN_PROGRESS,
                steps=[
                    step(
                        status=PlanStepStatus.PENDING
                    )
                ],
            ),
            status=PlanRunStatus.BLOCKED,
            validation_value=validation(valid=False),
        )
    )

    assert result.decision is (
        PlanEvaluationDecision
        .HUMAN_REVIEW_REQUIRED
    )
    assert result.human_review_recommended is True


def test_cancelled_plan_returns_cancelled_decision() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.CANCELLED,
                steps=[
                    step(
                        status=PlanStepStatus.SKIPPED
                    )
                ],
            ),
            status=PlanRunStatus.CANCELLED,
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.CANCELLED
    )


def test_active_plan_at_cycle_limit_requires_replanning() -> None:
    result = PlanEvaluator().evaluate(
        run_result(
            plan_value=plan(
                status=PlanStatus.IN_PROGRESS,
                steps=[
                    step(
                        status=PlanStepStatus.READY
                    )
                ],
            ),
            status=PlanRunStatus.CYCLE_LIMIT_REACHED,
        )
    )

    assert result.decision is (
        PlanEvaluationDecision.REPLAN_REQUIRED
    )
