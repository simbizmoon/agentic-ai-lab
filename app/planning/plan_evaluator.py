"""Deterministic evaluation of structured plan-run results."""

from __future__ import annotations

from app.schemas.plan import (
    PlanStatus,
    PlanStepStatus,
)
from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
    PlanEvaluationResult,
)
from app.schemas.plan_run import (
    PlanRunResult,
    PlanRunStatus,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionStatus,
)


class PlanEvaluator:
    """Evaluate whether a plan achieved its goal or needs action."""

    def evaluate(
        self,
        run_result: PlanRunResult,
    ) -> PlanEvaluationResult:
        """Return one deterministic evaluation."""

        failed_step_ids = self._failed_step_ids(
            run_result
        )
        incomplete_step_ids = [
            step.step_id
            for step in run_result.plan.steps
            if step.status
            not in {
                PlanStepStatus.COMPLETED,
                PlanStepStatus.SKIPPED,
            }
        ]

        if (
            run_result.status is PlanRunStatus.COMPLETED
            and run_result.plan.status
            is PlanStatus.COMPLETED
            and run_result.validation.valid
            and not failed_step_ids
            and not incomplete_step_ids
        ):
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision.GOAL_ACHIEVED
                ),
                codes=[
                    PlanEvaluationCode.PLAN_COMPLETED
                ],
                summary=(
                    "The plan completed with no failed "
                    "or incomplete steps."
                ),
                failed_step_ids=[],
                incomplete_step_ids=[],
                replan_recommended=False,
                human_review_recommended=False,
            )

        if (
            run_result.status is PlanRunStatus.CANCELLED
            or run_result.plan.status
            is PlanStatus.CANCELLED
        ):
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.CANCELLED,
                codes=[
                    PlanEvaluationCode.PLAN_CANCELLED
                ],
                summary="The plan was cancelled.",
                failed_step_ids=failed_step_ids,
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=False,
                human_review_recommended=False,
            )

        if not run_result.validation.valid:
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision
                    .HUMAN_REVIEW_REQUIRED
                ),
                codes=[
                    PlanEvaluationCode
                    .PLAN_VALIDATION_FAILED
                ],
                summary=(
                    "The resulting plan is structurally or "
                    "logically invalid."
                ),
                failed_step_ids=failed_step_ids,
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=False,
                human_review_recommended=True,
            )

        if failed_step_ids:
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision
                    .REPLAN_REQUIRED
                ),
                codes=[
                    PlanEvaluationCode
                    .STEP_EXECUTION_FAILED
                ],
                summary=(
                    "One or more plan steps failed during "
                    "execution."
                ),
                failed_step_ids=failed_step_ids,
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=True,
                human_review_recommended=False,
            )

        if (
            run_result.status
            is PlanRunStatus.CYCLE_LIMIT_REACHED
        ):
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision
                    .REPLAN_REQUIRED
                ),
                codes=[
                    PlanEvaluationCode
                    .CYCLE_LIMIT_REACHED
                ],
                summary=(
                    "The plan did not finish within the "
                    "configured cycle limit."
                ),
                failed_step_ids=[],
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=True,
                human_review_recommended=False,
            )

        if run_result.status is PlanRunStatus.BLOCKED:
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision
                    .REPLAN_REQUIRED
                ),
                codes=[
                    PlanEvaluationCode
                    .NO_EXECUTABLE_STEP
                ],
                summary=(
                    "The plan is blocked because no executable "
                    "step can be scheduled."
                ),
                failed_step_ids=[],
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=True,
                human_review_recommended=False,
            )

        if (
            run_result.plan.status is PlanStatus.FAILED
            and not failed_step_ids
        ):
            return PlanEvaluationResult(
                decision=(
                    PlanEvaluationDecision
                    .TERMINAL_FAILURE
                ),
                codes=[
                    PlanEvaluationCode
                    .PLAN_FAILED_WITHOUT_STEP_ERROR
                ],
                summary=(
                    "The plan is failed without a recorded "
                    "step execution failure."
                ),
                failed_step_ids=[],
                incomplete_step_ids=incomplete_step_ids,
                replan_recommended=False,
                human_review_recommended=True,
            )

        return PlanEvaluationResult(
            decision=PlanEvaluationDecision.CONTINUE,
            codes=[
                PlanEvaluationCode.PLAN_STILL_IN_PROGRESS
            ],
            summary=(
                "The plan remains in progress and can continue."
            ),
            failed_step_ids=failed_step_ids,
            incomplete_step_ids=incomplete_step_ids,
            replan_recommended=False,
            human_review_recommended=False,
        )

    @staticmethod
    def _failed_step_ids(
        run_result: PlanRunResult,
    ) -> list[str]:
        """Return unique failed step IDs in cycle order."""

        failed_step_ids: list[str] = []

        for cycle in run_result.cycles:
            for step_result in cycle.step_results:
                if (
                    step_result.status
                    is PlanStepExecutionStatus.FAILED
                    and step_result.step_id
                    not in failed_step_ids
                ):
                    failed_step_ids.append(
                        step_result.step_id
                    )

        for step in run_result.plan.steps:
            if (
                step.status is PlanStepStatus.FAILED
                and step.step_id not in failed_step_ids
            ):
                failed_step_ids.append(step.step_id)

        return failed_step_ids
