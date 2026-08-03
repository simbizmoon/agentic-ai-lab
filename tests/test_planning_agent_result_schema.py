"""Tests for integrated planning-agent result schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.created_plan import CreatedPlan
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
    PlanEvaluationResult,
)
from app.schemas.plan_run import (
    PlanRunResult,
    PlanRunStatus,
)
from app.schemas.plan_validation import (
    PlanValidationResult,
)
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationResult,
)
from app.schemas.planner_prompt import (
    PlannerPrompt,
    PlannerPromptKind,
    PlannerPromptMessage,
    PlannerPromptRole,
)
from app.schemas.planning_agent_result import (
    PlanningAgentResult,
)
from app.schemas.planning_result import PlanningResult

NOW = datetime(
    2026,
    8,
    3,
    23,
    0,
    tzinfo=UTC,
)


def completed_plan(
    *,
    plan_id: str = "plan-001",
) -> Plan:
    """Return one completed plan."""

    return Plan(
        plan_id=plan_id,
        goal="Complete one operation.",
        status=PlanStatus.COMPLETED,
        steps=[
            PlanStep(
                step_id="step-1",
                title="Execute",
                description="Execute the operation.",
                status=PlanStepStatus.COMPLETED,
                tool_name="python",
            )
        ],
        created_at=NOW,
        updated_at=NOW,
    )


def validation() -> PlanValidationResult:
    """Return one valid plan validation."""

    return PlanValidationResult(
        valid=True,
        issues=[],
        execution_order=["step-1"],
    )


def planning_result() -> PlanningResult:
    """Return one integrated planning result."""

    output = PlanDraftOutput(
        reasoning_summary="Use one step.",
        steps=[
            PlanStepDraft(
                step_id="step-1",
                title="Execute",
                description="Execute the operation.",
                tool_name="python",
            )
        ],
    )

    return PlanningResult(
        prompt=PlannerPrompt(
            kind=PlannerPromptKind.INITIAL_PLAN,
            messages=[
                PlannerPromptMessage(
                    role=PlannerPromptRole.SYSTEM,
                    content="System instructions.",
                ),
                PlannerPromptMessage(
                    role=PlannerPromptRole.USER,
                    content="Planning request.",
                ),
            ],
            maximum_steps=3,
            available_tools=["python"],
        ),
        planner_result=PlannerClientResult(
            output=output,
            validation=(
                PlannerOutputValidationResult(
                    valid=True,
                    issues=[],
                    execution_order=["step-1"],
                )
            ),
        ),
        created_plan=CreatedPlan(
            plan=completed_plan(),
            validation=validation(),
        ),
    )


def run_result(
    *,
    plan_id: str = "plan-001",
) -> PlanRunResult:
    """Return one completed run result."""

    return PlanRunResult(
        plan=completed_plan(plan_id=plan_id),
        validation=validation(),
        cycles=[],
        status=PlanRunStatus.COMPLETED,
        message="Plan completed.",
        executed_step_ids=[],
    )


def evaluation() -> PlanEvaluationResult:
    """Return one successful evaluation."""

    return PlanEvaluationResult(
        decision=PlanEvaluationDecision.GOAL_ACHIEVED,
        codes=[PlanEvaluationCode.PLAN_COMPLETED],
        summary="The plan completed.",
        failed_step_ids=[],
        incomplete_step_ids=[],
        replan_recommended=False,
        human_review_recommended=False,
    )


def test_result_accepts_consistent_pipeline() -> None:
    result = PlanningAgentResult(
        planning=planning_result(),
        run=run_result(),
        evaluation=evaluation(),
    )

    assert result.evaluation.decision is (
        PlanEvaluationDecision.GOAL_ACHIEVED
    )


def test_result_rejects_different_plan_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="same plan",
    ):
        PlanningAgentResult(
            planning=planning_result(),
            run=run_result(plan_id="plan-999"),
            evaluation=evaluation(),
        )


def test_goal_achieved_requires_completed_plan() -> None:
    active_run = run_result()
    active_run.plan.status = PlanStatus.IN_PROGRESS

    with pytest.raises(
        ValidationError,
        match="requires a completed plan",
    ):
        PlanningAgentResult(
            planning=planning_result(),
            run=active_run,
            evaluation=evaluation(),
        )


def test_result_rejects_unknown_failed_step() -> None:
    invalid_evaluation = evaluation().model_copy(
        update={
            "decision": (
                PlanEvaluationDecision.REPLAN_REQUIRED
            ),
            "codes": [
                PlanEvaluationCode.STEP_EXECUTION_FAILED
            ],
            "failed_step_ids": ["missing-step"],
            "incomplete_step_ids": [],
            "replan_recommended": True,
        }
    )

    with pytest.raises(
        ValidationError,
        match="failed steps must reference",
    ):
        PlanningAgentResult(
            planning=planning_result(),
            run=run_result(),
            evaluation=invalid_evaluation,
        )
