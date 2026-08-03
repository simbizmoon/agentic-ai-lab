"""Integrated planning, execution, and evaluation pipeline."""

from __future__ import annotations

from app.planning.plan_evaluator import PlanEvaluator
from app.planning.plan_runner import PlanRunner
from app.planning.planning_service import (
    PlanningService,
    PlanningServiceError,
)
from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.plan_run import PlanRunStatus
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)
from app.schemas.planning_agent_result import (
    PlanningAgentResult,
)
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)


class PlanningAgentPipelineError(RuntimeError):
    """Raised when the planning-agent pipeline cannot run."""


class PlanningAgentPipeline:
    """Plan, execute, and evaluate one agent goal."""

    def __init__(
        self,
        *,
        planning_service: PlanningService,
        plan_runner: PlanRunner,
        plan_evaluator: PlanEvaluator,
    ) -> None:
        self._planning_service = planning_service
        self._plan_runner = plan_runner
        self._plan_evaluator = plan_evaluator

    @property
    def planning_service(self) -> PlanningService:
        """Return the configured planning service."""

        return self._planning_service

    @property
    def plan_runner(self) -> PlanRunner:
        """Return the configured plan runner."""

        return self._plan_runner

    @property
    def plan_evaluator(self) -> PlanEvaluator:
        """Return the configured plan evaluator."""

        return self._plan_evaluator

    def run(
        self,
        request: PlanningAgentRequest,
        *,
        trace_session: AgentTraceSession | None = None,
        attempt_number: int = 1,
    ) -> PlanningAgentResult:
        """Plan, execute, and evaluate one request."""

        if attempt_number < 1:
            raise ValueError(
                "attempt_number must be at least 1"
            )

        self._emit(
            trace_session=trace_session,
            event_type=AgentTraceEventType.PLANNING_STARTED,
            message="Planning started.",
            attempt_number=attempt_number,
        )

        try:
            planning_result = (
                self.planning_service.create_plan(
                    request.planning
                )
            )
        except PlanningServiceError as exc:
            self._emit(
                trace_session=trace_session,
                event_type=(
                    AgentTraceEventType.PLANNING_FAILED
                ),
                message="Planning failed.",
                attempt_number=attempt_number,
                metadata={"error": str(exc)},
            )
            raise PlanningAgentPipelineError(
                "planning stage failed"
            ) from exc

        plan_id = (
            planning_result.created_plan.plan.plan_id
        )

        self._emit(
            trace_session=trace_session,
            event_type=(
                AgentTraceEventType.PLANNING_COMPLETED
            ),
            message="Planning completed.",
            plan_id=plan_id,
            attempt_number=attempt_number,
        )

        lifecycle_result = (
            self.plan_runner
            .execution_service
            .lifecycle
            .start_plan(
                planning_result.created_plan.plan
            )
        )

        self._emit(
            trace_session=trace_session,
            event_type=AgentTraceEventType.PLAN_STARTED,
            message="Plan execution started.",
            plan_id=plan_id,
            attempt_number=attempt_number,
        )

        run_result = self.plan_runner.run(
            plan=lifecycle_result.plan,
            request=request.execution,
        )

        self._emit_run_result(
            trace_session=trace_session,
            run_status=run_result.status,
            plan_id=plan_id,
            attempt_number=attempt_number,
            cycle_count=len(run_result.cycles),
        )

        evaluation = self.plan_evaluator.evaluate(
            run_result
        )

        self._emit(
            trace_session=trace_session,
            event_type=(
                AgentTraceEventType.EVALUATION_COMPLETED
            ),
            message="Plan evaluation completed.",
            plan_id=plan_id,
            attempt_number=attempt_number,
            metadata={
                "decision": evaluation.decision.value,
                "codes": [
                    code.value
                    for code in evaluation.codes
                ],
            },
        )

        return PlanningAgentResult(
            planning=planning_result,
            run=run_result,
            evaluation=evaluation,
        )

    @staticmethod
    def _emit(
        *,
        trace_session: AgentTraceSession | None,
        event_type: AgentTraceEventType,
        message: str,
        plan_id: str | None = None,
        attempt_number: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Emit one trace event when tracing is enabled."""

        if trace_session is None:
            return

        trace_session.emit(
            event_type=event_type,
            message=message,
            plan_id=plan_id,
            attempt_number=attempt_number,
            metadata=metadata,
        )

    @classmethod
    def _emit_run_result(
        cls,
        *,
        trace_session: AgentTraceSession | None,
        run_status: PlanRunStatus,
        plan_id: str,
        attempt_number: int,
        cycle_count: int,
    ) -> None:
        """Emit the trace event matching one run result."""

        event_types = {
            PlanRunStatus.COMPLETED: (
                AgentTraceEventType.PLAN_COMPLETED
            ),
            PlanRunStatus.FAILED: (
                AgentTraceEventType.PLAN_FAILED
            ),
            PlanRunStatus.CANCELLED: (
                AgentTraceEventType.PLAN_CANCELLED
            ),
            PlanRunStatus.BLOCKED: (
                AgentTraceEventType.PLAN_BLOCKED
            ),
            PlanRunStatus.CYCLE_LIMIT_REACHED: (
                AgentTraceEventType.PLAN_BLOCKED
            ),
        }

        cls._emit(
            trace_session=trace_session,
            event_type=event_types[run_status],
            message=f"Plan execution ended: {run_status.value}.",
            plan_id=plan_id,
            attempt_number=attempt_number,
            metadata={
                "run_status": run_status.value,
                "cycle_count": cycle_count,
            },
        )

