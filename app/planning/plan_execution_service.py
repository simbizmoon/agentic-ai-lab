"""End-to-end execution of scheduled plan steps."""

from __future__ import annotations

from app.planning.plan_lifecycle_service import (
    PlanLifecycleService,
)
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import (
    PlanStepExecutor,
)
from app.schemas.agent_trace import AgentTraceEventType
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
from app.tracing.agent_trace_session import (
    AgentTraceSession,
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

    @property
    def scheduler(self) -> PlanScheduler:
        """Return the configured plan scheduler."""

        return self._scheduler

    @property
    def lifecycle(self) -> PlanLifecycleService:
        """Return the configured lifecycle service."""

        return self._lifecycle

    @property
    def step_executor(self) -> PlanStepExecutor:
        """Return the configured step executor."""

        return self._step_executor

    def execute_next(
        self,
        *,
        plan: Plan,
        schedule_request: PlanScheduleRequest | None = None,
        trace_session: AgentTraceSession | None = None,
        attempt_number: int | None = None,
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
            step = self._get_step(
                plan=current_plan,
                step_id=step_id,
            )

            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.STEP_STARTED,
                message=f"Step {step_id} started.",
                plan_id=current_plan.plan_id,
                step_id=step_id,
                tool_name=step.tool_name,
                attempt_number=attempt_number,
            )

            started = self._lifecycle.start_step(
                current_plan,
                step_id=step_id,
            )
            current_plan = started.plan

            step = self._get_step(
                plan=current_plan,
                step_id=step_id,
            )

            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.TOOL_STARTED,
                message=(
                    f"Tool execution started for step "
                    f"{step_id}."
                ),
                plan_id=current_plan.plan_id,
                step_id=step_id,
                tool_name=step.tool_name,
                attempt_number=attempt_number,
            )

            execution = self._step_executor.execute(step)
            step_results.append(execution)

            if (
                execution.status
                is PlanStepExecutionStatus.SUCCEEDED
            ):
                self._emit(
                    trace_session=trace_session,
                    event_type=(
                        AgentTraceEventType.TOOL_COMPLETED
                    ),
                    message=(
                        f"Tool execution completed for step "
                        f"{step_id}."
                    ),
                    plan_id=current_plan.plan_id,
                    step_id=step_id,
                    tool_name=execution.tool_name,
                    attempt_number=attempt_number,
                )

                completed = self._lifecycle.complete_step(
                    current_plan,
                    step_id=step_id,
                )
                current_plan = completed.plan

                self._emit(
                    trace_session=trace_session,
                    event_type=(
                        AgentTraceEventType.STEP_COMPLETED
                    ),
                    message=f"Step {step_id} completed.",
                    plan_id=current_plan.plan_id,
                    step_id=step_id,
                    tool_name=execution.tool_name,
                    attempt_number=attempt_number,
                )
                continue

            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.TOOL_FAILED,
                message=(
                    f"Tool execution failed for step "
                    f"{step_id}."
                ),
                plan_id=current_plan.plan_id,
                step_id=step_id,
                tool_name=execution.tool_name,
                attempt_number=attempt_number,
                metadata={
                    "error_message": execution.error_message
                },
            )

            failed = self._lifecycle.fail_step(
                current_plan,
                step_id=step_id,
            )
            current_plan = failed.plan

            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.STEP_FAILED,
                message=f"Step {step_id} failed.",
                plan_id=current_plan.plan_id,
                step_id=step_id,
                tool_name=execution.tool_name,
                attempt_number=attempt_number,
                metadata={
                    "error_message": execution.error_message
                },
            )

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

    @staticmethod
    def _emit(
        *,
        trace_session: AgentTraceSession | None,
        event_type: AgentTraceEventType,
        message: str,
        plan_id: str,
        step_id: str,
        tool_name: str | None,
        attempt_number: int | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Emit one execution event when tracing is enabled."""

        if trace_session is None:
            return

        trace_session.emit(
            event_type=event_type,
            message=message,
            plan_id=plan_id,
            step_id=step_id,
            tool_name=tool_name,
            attempt_number=attempt_number,
            metadata=metadata,
        )

