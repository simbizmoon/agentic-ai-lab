"""End-to-end execution of scheduled plan steps."""

from __future__ import annotations

from app.planning.plan_lifecycle_service import (
    PlanLifecycleService,
)
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import (
    PlanStepExecutor,
)
from app.schemas.plan import Plan, PlanStep
from app.schemas.plan_execution import (
    PlanExecutionResult,
    PlanExecutionStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleRequest,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionStatus,
)


class PlanExecutionService:
    """Schedule, execute, and apply lifecycle transitions."""

    def __init__(
        self,
        *,
        scheduler: PlanScheduler,
        lifecycle: PlanLifecycleService,
        step_executor: PlanStepExecutor,
    ) -> None:
        self._scheduler = scheduler
        self._lifecycle = lifecycle
        self._step_executor = step_executor

    def execute_next(
        self,
        *,
        plan: Plan,
        schedule_request: PlanScheduleRequest | None = None,
    ) -> PlanExecutionResult:
        """Execute the next scheduled step or steps."""

        schedule = self._scheduler.schedule(
            plan=plan,
            request=schedule_request,
        )

        if not schedule.selected_step_ids:
            validation = self._scheduler.validator.validate(plan)

            return PlanExecutionResult(
                plan=plan.model_copy(deep=True),
                validation=validation,
                schedule=schedule,
                step_results=[],
                status=(
                    PlanExecutionStatus
                    .NOTHING_SCHEDULED
                ),
            )

        current_plan = plan.model_copy(deep=True)
        step_results = []
        overall_status = (
            PlanExecutionStatus.STEP_SUCCEEDED
        )

        for step_id in schedule.selected_step_ids:
            started = self._lifecycle.start_step(
                current_plan,
                step_id=step_id,
            )
            current_plan = started.plan

            step = self._get_step(
                plan=current_plan,
                step_id=step_id,
            )
            execution = self._step_executor.execute(step)
            step_results.append(execution)

            if (
                execution.status
                is PlanStepExecutionStatus.SUCCEEDED
            ):
                completed = self._lifecycle.complete_step(
                    current_plan,
                    step_id=step_id,
                )
                current_plan = completed.plan
                continue

            failed = self._lifecycle.fail_step(
                current_plan,
                step_id=step_id,
            )
            current_plan = failed.plan
            overall_status = (
                PlanExecutionStatus.STEP_FAILED
            )
            break

        validation = self._scheduler.validator.validate(
            current_plan
        )

        return PlanExecutionResult(
            plan=current_plan,
            validation=validation,
            schedule=schedule,
            step_results=step_results,
            status=overall_status,
        )

    @staticmethod
    def _get_step(
        *,
        plan: Plan,
        step_id: str,
    ) -> PlanStep:
        """Return one step from a plan."""

        for step in plan.steps:
            if step.step_id == step_id:
                return step

        raise RuntimeError(
            f"scheduled step not found: {step_id}"
        )
