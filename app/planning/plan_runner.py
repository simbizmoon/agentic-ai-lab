"""Repeated execution of structured agent plans."""

from __future__ import annotations

from typing import ClassVar

from app.planning.plan_execution_service import (
    PlanExecutionService,
)
from app.schemas.plan import Plan, PlanStatus
from app.schemas.plan_execution import (
    PlanExecutionResult,
    PlanExecutionStatus,
)
from app.schemas.plan_run import (
    PlanRunRequest,
    PlanRunResult,
    PlanRunStatus,
)
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)


class PlanRunner:
    """Run execution cycles until a plan reaches a stop condition."""

    _TERMINAL_STATUS_MAP: ClassVar[
        dict[PlanStatus, PlanRunStatus]
    ] = {
        PlanStatus.COMPLETED: PlanRunStatus.COMPLETED,
        PlanStatus.FAILED: PlanRunStatus.FAILED,
        PlanStatus.CANCELLED: PlanRunStatus.CANCELLED,
    }

    def __init__(
        self,
        *,
        execution_service: PlanExecutionService,
    ) -> None:
        self._execution_service = execution_service

    @property
    def execution_service(
        self,
    ) -> PlanExecutionService:
        """Return the configured execution service."""

        return self._execution_service

    def run(
        self,
        *,
        plan: Plan,
        request: PlanRunRequest | None = None,
        trace_session: AgentTraceSession | None = None,
        attempt_number: int | None = None,
    ) -> PlanRunResult:
        """Run a plan until terminal, blocked, or cycle-limited."""

        options = request or PlanRunRequest()
        current_plan = plan.model_copy(deep=True)
        cycles: list[PlanExecutionResult] = []
        executed_step_ids: list[str] = []

        terminal_result = self._terminal_result(
            plan=current_plan,
            cycles=cycles,
            executed_step_ids=executed_step_ids,
        )

        if terminal_result is not None:
            return terminal_result

        for _ in range(options.maximum_cycles):
            previous_signature = self._plan_signature(
                current_plan
            )

            cycle = self.execution_service.execute_next(
                plan=current_plan,
                schedule_request=(
                    options.schedule_request
                ),
                trace_session=trace_session,
                attempt_number=attempt_number,
            )
            cycles.append(cycle)
            current_plan = cycle.plan

            for step_result in cycle.step_results:
                if (
                    step_result.step_id
                    not in executed_step_ids
                ):
                    executed_step_ids.append(
                        step_result.step_id
                    )

            terminal_result = self._terminal_result(
                plan=current_plan,
                cycles=cycles,
                executed_step_ids=executed_step_ids,
            )

            if terminal_result is not None:
                return terminal_result

            if (
                cycle.status
                is PlanExecutionStatus.NOTHING_SCHEDULED
            ):
                return self._result(
                    plan=current_plan,
                    cycles=cycles,
                    executed_step_ids=executed_step_ids,
                    status=PlanRunStatus.BLOCKED,
                    message=(
                        "No executable plan step was scheduled."
                    ),
                )

            if (
                options.stop_on_no_progress
                and self._plan_signature(current_plan)
                == previous_signature
            ):
                return self._result(
                    plan=current_plan,
                    cycles=cycles,
                    executed_step_ids=executed_step_ids,
                    status=PlanRunStatus.BLOCKED,
                    message=(
                        "Plan execution made no observable progress."
                    ),
                )

        return self._result(
            plan=current_plan,
            cycles=cycles,
            executed_step_ids=executed_step_ids,
            status=PlanRunStatus.CYCLE_LIMIT_REACHED,
            message=(
                "Plan execution reached the maximum "
                "number of cycles."
            ),
        )

    def _terminal_result(
        self,
        *,
        plan: Plan,
        cycles: list[PlanExecutionResult],
        executed_step_ids: list[str],
    ) -> PlanRunResult | None:
        """Return a terminal result when the plan is terminal."""

        run_status = self._TERMINAL_STATUS_MAP.get(
            plan.status
        )

        if run_status is None:
            return None

        messages = {
            PlanRunStatus.COMPLETED: (
                "Plan execution completed successfully."
            ),
            PlanRunStatus.FAILED: (
                "Plan execution stopped after a failure."
            ),
            PlanRunStatus.CANCELLED: (
                "Plan execution was cancelled."
            ),
        }

        return self._result(
            plan=plan,
            cycles=cycles,
            executed_step_ids=executed_step_ids,
            status=run_status,
            message=messages[run_status],
        )

    def _result(
        self,
        *,
        plan: Plan,
        cycles: list[PlanExecutionResult],
        executed_step_ids: list[str],
        status: PlanRunStatus,
        message: str,
    ) -> PlanRunResult:
        """Validate and package one plan-run result."""

        validation = (
            self.execution_service
            .scheduler
            .validator
            .validate(plan)
        )

        return PlanRunResult(
            plan=plan,
            validation=validation,
            cycles=cycles,
            status=status,
            message=message,
            executed_step_ids=executed_step_ids,
        )

    @staticmethod
    def _plan_signature(
        plan: Plan,
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Return a deterministic observable plan signature."""

        return (
            plan.status.value,
            tuple(
                (
                    step.step_id,
                    step.status.value,
                )
                for step in plan.steps
            ),
        )
