"""Build deterministic replanning context from plan-run results."""

from __future__ import annotations

from typing import Any, ClassVar

from app.schemas.plan import PlanStep, PlanStepStatus
from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
    PlanEvaluationResult,
)
from app.schemas.plan_run import PlanRunResult
from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
)
from app.schemas.replan import (
    ReplanRequest,
    ReplanStepSummary,
)


class ReplanContextError(RuntimeError):
    """Raised when valid replanning context cannot be built."""


class ReplanContextService:
    """Convert previous plan execution into replanning input."""

    _REPLAN_DECISIONS: ClassVar[
        set[PlanEvaluationDecision]
    ] = {
        PlanEvaluationDecision.REPLAN_REQUIRED,
        PlanEvaluationDecision.HUMAN_REVIEW_REQUIRED,
        PlanEvaluationDecision.TERMINAL_FAILURE,
    }

    def build(
        self,
        *,
        run_result: PlanRunResult,
        evaluation: PlanEvaluationResult,
        maximum_steps: int | None = None,
    ) -> ReplanRequest:
        """Build one deterministic request for replanning."""

        if (
            evaluation.decision
            not in self._REPLAN_DECISIONS
        ):
            raise ReplanContextError(
                "evaluation does not require replanning context"
            )

        execution_by_step = self._execution_results(
            run_result
        )

        completed_steps: list[ReplanStepSummary] = []
        failed_steps: list[ReplanStepSummary] = []
        incomplete_steps: list[ReplanStepSummary] = []

        for step in run_result.plan.steps:
            execution = execution_by_step.get(step.step_id)
            summary = self._step_summary(
                step=step,
                execution=execution,
            )

            if step.status in {
                PlanStepStatus.COMPLETED,
                PlanStepStatus.SKIPPED,
            }:
                completed_steps.append(summary)
            elif step.status is PlanStepStatus.FAILED:
                failed_steps.append(summary)
            else:
                incomplete_steps.append(summary)

        metadata = run_result.plan.metadata

        constraints = self._string_list(
            metadata.get("constraints")
        )
        available_tools = self._string_list(
            metadata.get("available_tools")
        )

        configured_maximum_steps = (
            maximum_steps
            if maximum_steps is not None
            else max(
                len(run_result.plan.steps),
                1,
            )
        )

        return ReplanRequest(
            original_plan_id=run_result.plan.plan_id,
            goal=run_result.plan.goal,
            evaluation_decision=evaluation.decision,
            evaluation_codes=list(evaluation.codes),
            evaluation_summary=evaluation.summary,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            incomplete_steps=incomplete_steps,
            constraints=constraints,
            available_tools=available_tools,
            maximum_steps=configured_maximum_steps,
            previous_cycle_count=len(run_result.cycles),
            metadata={
                "previous_run_status": (
                    run_result.status.value
                ),
                "previous_plan_status": (
                    run_result.plan.status.value
                ),
                "replan_recommended": (
                    evaluation.replan_recommended
                ),
                "human_review_recommended": (
                    evaluation.human_review_recommended
                ),
            },
        )

    @staticmethod
    def _execution_results(
        run_result: PlanRunResult,
    ) -> dict[str, PlanStepExecutionResult]:
        """Return the latest execution result for each step."""

        results: dict[str, PlanStepExecutionResult] = {}

        for cycle in run_result.cycles:
            for execution in cycle.step_results:
                results[execution.step_id] = execution

        return results

    @staticmethod
    def _step_summary(
        *,
        step: PlanStep,
        execution: PlanStepExecutionResult | None,
    ) -> ReplanStepSummary:
        """Convert one plan step into a replan summary."""

        output: Any | None = None
        error_message: str | None = None

        if execution is not None:
            error_message = execution.error_message

            if execution.tool_result is not None:
                output = execution.tool_result.output

        return ReplanStepSummary(
            step_id=step.step_id,
            title=step.title,
            description=step.description,
            status=step.status.value,
            tool_name=step.tool_name,
            dependencies=list(step.dependencies),
            output=output,
            error_message=error_message,
        )

    @staticmethod
    def _string_list(
        value: object,
    ) -> list[str]:
        """Return a defensive string list from metadata."""

        if not isinstance(value, list):
            return []

        return [
            item
            for item in value
            if isinstance(item, str)
            and item.strip()
        ]
