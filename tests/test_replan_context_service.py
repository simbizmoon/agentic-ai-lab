"""Tests for deterministic replanning context extraction."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.planning.replan_context_service import (
    ReplanContextError,
    ReplanContextService,
)
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
    PlanEvaluationResult,
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
    PlanValidationResult,
)
from app.schemas.tool_execution import (
    ToolExecutionResult,
    ToolExecutionStatus,
)

NOW = datetime(
    2026,
    8,
    3,
    21,
    0,
    tzinfo=UTC,
)


def step(
    *,
    step_id: str,
    status: PlanStepStatus,
    dependencies: list[str] | None = None,
) -> PlanStep:
    """Return one plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        status=status,
        dependencies=dependencies or [],
        tool_name="python",
    )


def plan() -> Plan:
    """Return one partially failed plan."""

    return Plan(
        plan_id="plan-001",
        goal="Complete the requested workflow.",
        status=PlanStatus.FAILED,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.FAILED,
                dependencies=["step-1"],
            ),
            step(
                step_id="step-3",
                status=PlanStepStatus.PENDING,
                dependencies=["step-2"],
            ),
        ],
        created_at=NOW,
        updated_at=NOW,
        metadata={
            "constraints": ["Run all tests."],
            "available_tools": ["python", "pytest"],
        },
    )


def validation() -> PlanValidationResult:
    """Return one valid plan validation result."""

    return PlanValidationResult(
        valid=True,
        issues=[],
        execution_order=[
            "step-1",
            "step-2",
            "step-3",
        ],
    )


def failed_cycle() -> PlanExecutionResult:
    """Return one failed execution cycle."""

    return PlanExecutionResult(
        plan=plan(),
        validation=validation(),
        schedule=PlanScheduleResult(
            selected_step_ids=["step-2"],
            ready_step_ids=["step-2"],
            active_step_ids=[],
            reason=PlanScheduleReason.STEPS_SELECTED,
        ),
        step_results=[
            PlanStepExecutionResult(
                step_id="step-2",
                tool_name="python",
                status=PlanStepExecutionStatus.FAILED,
                tool_result=ToolExecutionResult(
                    tool_name="python",
                    status=ToolExecutionStatus.FAILED,
                    error_message="Command failed.",
                ),
                error_message="Command failed.",
            )
        ],
        status=PlanExecutionStatus.STEP_FAILED,
    )


def run_result() -> PlanRunResult:
    """Return one failed plan-run result."""

    return PlanRunResult(
        plan=plan(),
        validation=validation(),
        cycles=[failed_cycle()],
        status=PlanRunStatus.FAILED,
        message="The plan failed.",
        executed_step_ids=["step-2"],
    )


def evaluation(
    *,
    decision: PlanEvaluationDecision = (
        PlanEvaluationDecision.REPLAN_REQUIRED
    ),
) -> PlanEvaluationResult:
    """Return one evaluation result."""

    return PlanEvaluationResult(
        decision=decision,
        codes=[
            PlanEvaluationCode.STEP_EXECUTION_FAILED
        ],
        summary="Step step-2 failed.",
        failed_step_ids=["step-2"],
        incomplete_step_ids=[
            "step-2",
            "step-3",
        ],
        replan_recommended=(
            decision
            is PlanEvaluationDecision.REPLAN_REQUIRED
        ),
        human_review_recommended=(
            decision
            is PlanEvaluationDecision
            .HUMAN_REVIEW_REQUIRED
        ),
    )


def test_service_extracts_step_groups() -> None:
    result = ReplanContextService().build(
        run_result=run_result(),
        evaluation=evaluation(),
    )

    assert [
        item.step_id
        for item in result.completed_steps
    ] == ["step-1"]
    assert [
        item.step_id
        for item in result.failed_steps
    ] == ["step-2"]
    assert [
        item.step_id
        for item in result.incomplete_steps
    ] == ["step-3"]


def test_service_preserves_failure_details() -> None:
    result = ReplanContextService().build(
        run_result=run_result(),
        evaluation=evaluation(),
    )

    failed = result.failed_steps[0]

    assert failed.error_message == "Command failed."
    assert failed.tool_name == "python"


def test_service_extracts_plan_constraints() -> None:
    result = ReplanContextService().build(
        run_result=run_result(),
        evaluation=evaluation(),
    )

    assert result.constraints == ["Run all tests."]
    assert result.available_tools == [
        "python",
        "pytest",
    ]


def test_service_records_previous_execution_context() -> None:
    result = ReplanContextService().build(
        run_result=run_result(),
        evaluation=evaluation(),
    )

    assert result.previous_cycle_count == 1
    assert result.metadata[
        "previous_run_status"
    ] == "failed"
    assert result.metadata[
        "previous_plan_status"
    ] == "failed"


def test_service_accepts_explicit_maximum_steps() -> None:
    result = ReplanContextService().build(
        run_result=run_result(),
        evaluation=evaluation(),
        maximum_steps=8,
    )

    assert result.maximum_steps == 8


def test_service_rejects_goal_achieved_evaluation() -> None:
    achieved = PlanEvaluationResult(
        decision=PlanEvaluationDecision.GOAL_ACHIEVED,
        codes=[PlanEvaluationCode.PLAN_COMPLETED],
        summary="The plan completed.",
        failed_step_ids=[],
        incomplete_step_ids=[],
        replan_recommended=False,
        human_review_recommended=False,
    )

    with pytest.raises(
        ReplanContextError,
        match="does not require replanning context",
    ):
        ReplanContextService().build(
            run_result=run_result(),
            evaluation=achieved,
        )


def test_service_does_not_mutate_source_result() -> None:
    source = run_result()

    result = ReplanContextService().build(
        run_result=source,
        evaluation=evaluation(),
    )

    result.constraints.append("New constraint.")

    assert source.plan.metadata["constraints"] == [
        "Run all tests."
    ]
