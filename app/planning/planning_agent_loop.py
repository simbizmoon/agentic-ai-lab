"""Bounded automatic replanning for planning agents."""

from __future__ import annotations

from app.planning.planning_agent_pipeline import (
    PlanningAgentPipeline,
    PlanningAgentPipelineError,
)
from app.planning.replan_context_service import (
    ReplanContextError,
    ReplanContextService,
)
from app.planning.replanning_service import (
    ReplanningService,
    ReplanningServiceError,
)
from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
)
from app.schemas.planning_agent_loop import (
    PlanningAgentAttempt,
    PlanningAgentLoopRequest,
    PlanningAgentLoopResult,
    PlanningAgentLoopStatus,
)
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)


class PlanningAgentLoopError(RuntimeError):
    """Raised when automatic planning cannot continue safely."""


class PlanningAgentLoop:
    """Run an initial plan and bounded replacement plans."""

    def __init__(
        self,
        *,
        pipeline: PlanningAgentPipeline,
        replan_context_service: ReplanContextService,
        replanning_service: ReplanningService,
    ) -> None:
        self._pipeline = pipeline
        self._replan_context_service = (
            replan_context_service
        )
        self._replanning_service = replanning_service

    @property
    def pipeline(self) -> PlanningAgentPipeline:
        """Return the configured planning pipeline."""

        return self._pipeline

    @property
    def replan_context_service(
        self,
    ) -> ReplanContextService:
        """Return the configured replan-context service."""

        return self._replan_context_service

    @property
    def replanning_service(
        self,
    ) -> ReplanningService:
        """Return the configured replanning service."""

        return self._replanning_service

    def run(
        self,
        request: PlanningAgentLoopRequest,
        *,
        trace_session: AgentTraceSession | None = None,
    ) -> PlanningAgentLoopResult:
        """Run initial planning and bounded replanning."""

        self._emit(
            trace_session=trace_session,
            event_type=AgentTraceEventType.AGENT_STARTED,
            message="Planning agent started.",
            attempt_number=1,
            metadata={
                "maximum_replans": request.maximum_replans
            },
        )

        try:
            initial_result = self._pipeline.run(
                request.initial,
                trace_session=trace_session,
                attempt_number=1,
            )
        except PlanningAgentPipelineError as exc:
            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.AGENT_FAILED,
                message="Initial planning pipeline failed.",
                attempt_number=1,
                metadata={"error": str(exc)},
            )
            raise PlanningAgentLoopError(
                "initial planning pipeline failed"
            ) from exc

        attempts = [
            PlanningAgentAttempt(
                attempt_number=1,
                planning=initial_result.planning,
                run=initial_result.run,
                evaluation=initial_result.evaluation,
                source_plan_id=None,
            )
        ]

        terminal_status = self._terminal_status(
            initial_result.evaluation.decision
        )

        if terminal_status is not None:
            self._emit_terminal(
                trace_session=trace_session,
                status=terminal_status,
                plan_id=initial_result.run.plan.plan_id,
                attempt_number=1,
            )

            return PlanningAgentLoopResult(
                attempts=attempts,
                status=terminal_status,
                trace_id=(
                    trace_session.trace_id
                    if trace_session is not None
                    else None
                ),
            )

        for replan_index in range(
            request.maximum_replans
        ):
            previous = attempts[-1]

            if (
                previous.evaluation.decision
                is not PlanEvaluationDecision.REPLAN_REQUIRED
            ):
                break

            attempt_number = replan_index + 2

            self._emit(
                trace_session=trace_session,
                event_type=(
                    AgentTraceEventType.REPLANNING_STARTED
                ),
                message="Replacement planning started.",
                plan_id=previous.run.plan.plan_id,
                attempt_number=attempt_number,
                metadata={
                    "source_plan_id": (
                        previous.run.plan.plan_id
                    )
                },
            )

            try:
                replan_request = (
                    self._replan_context_service.build(
                        run_result=previous.run,
                        evaluation=previous.evaluation,
                    )
                )
                planning_result = (
                    self._replanning_service.create_plan(
                        replan_request
                    )
                )
            except (
                ReplanContextError,
                ReplanningServiceError,
            ) as exc:
                self._emit(
                    trace_session=trace_session,
                    event_type=(
                        AgentTraceEventType
                        .REPLANNING_FAILED
                    ),
                    message="Replacement planning failed.",
                    plan_id=previous.run.plan.plan_id,
                    attempt_number=attempt_number,
                    metadata={"error": str(exc)},
                )
                self._emit(
                    trace_session=trace_session,
                    event_type=AgentTraceEventType.AGENT_FAILED,
                    message="Planning agent failed.",
                    plan_id=previous.run.plan.plan_id,
                    attempt_number=attempt_number,
                )
                raise PlanningAgentLoopError(
                    "replacement planning failed"
                ) from exc

            replacement_plan_id = (
                planning_result.created_plan.plan.plan_id
            )

            self._emit(
                trace_session=trace_session,
                event_type=(
                    AgentTraceEventType.REPLANNING_COMPLETED
                ),
                message="Replacement planning completed.",
                plan_id=replacement_plan_id,
                attempt_number=attempt_number,
                metadata={
                    "source_plan_id": (
                        previous.run.plan.plan_id
                    )
                },
            )

            lifecycle_result = (
                self._pipeline
                .plan_runner
                .execution_service
                .lifecycle
                .start_plan(
                    planning_result.created_plan.plan
                )
            )

            self._emit(
                trace_session=trace_session,
                event_type=AgentTraceEventType.PLAN_STARTED,
                message="Replacement plan execution started.",
                plan_id=replacement_plan_id,
                attempt_number=attempt_number,
            )

            run_result = self._pipeline.plan_runner.run(
                plan=lifecycle_result.plan,
                request=request.initial.execution,
                trace_session=trace_session,
                attempt_number=attempt_number,
            )
            self._emit_run_result(
                trace_session=trace_session,
                run_status=run_result.status,
                plan_id=replacement_plan_id,
                attempt_number=attempt_number,
                cycle_count=len(run_result.cycles),
            )

            evaluation = (
                self._pipeline.plan_evaluator.evaluate(
                    run_result
                )
            )

            self._emit(
                trace_session=trace_session,
                event_type=(
                    AgentTraceEventType.EVALUATION_COMPLETED
                ),
                message="Replacement plan evaluation completed.",
                plan_id=replacement_plan_id,
                attempt_number=attempt_number,
                metadata={
                    "decision": evaluation.decision.value,
                    "codes": [
                        code.value
                        for code in evaluation.codes
                    ],
                },
            )

            attempts.append(
                PlanningAgentAttempt(
                    attempt_number=attempt_number,
                    planning=planning_result,
                    run=run_result,
                    evaluation=evaluation,
                    source_plan_id=(
                        previous.run.plan.plan_id
                    ),
                )
            )

            terminal_status = self._terminal_status(
                evaluation.decision
            )

            if terminal_status is not None:
                self._emit_terminal(
                    trace_session=trace_session,
                    status=terminal_status,
                    plan_id=replacement_plan_id,
                    attempt_number=attempt_number,
                )

                return PlanningAgentLoopResult(
                    attempts=attempts,
                    status=terminal_status,
                    trace_id=(
                        trace_session.trace_id
                        if trace_session is not None
                        else None
                    ),
                )

        final_attempt = attempts[-1]

        self._emit(
            trace_session=trace_session,
            event_type=(
                AgentTraceEventType.REPLAN_LIMIT_REACHED
            ),
            message="Maximum replanning attempts reached.",
            plan_id=final_attempt.run.plan.plan_id,
            attempt_number=final_attempt.attempt_number,
            metadata={
                "maximum_replans": request.maximum_replans
            },
        )
        self._emit(
            trace_session=trace_session,
            event_type=AgentTraceEventType.AGENT_FAILED,
            message="Planning agent stopped at replan limit.",
            plan_id=final_attempt.run.plan.plan_id,
            attempt_number=final_attempt.attempt_number,
        )

        return PlanningAgentLoopResult(
            attempts=attempts,
            status=(
                PlanningAgentLoopStatus
                .REPLAN_LIMIT_REACHED
            ),
            trace_id=(
                trace_session.trace_id
                if trace_session is not None
                else None
            ),
        )

    @staticmethod
    def _terminal_status(
        decision: PlanEvaluationDecision,
    ) -> PlanningAgentLoopStatus | None:
        """Map terminal evaluations to loop outcomes."""

        status_map = {
            PlanEvaluationDecision.GOAL_ACHIEVED: (
                PlanningAgentLoopStatus.GOAL_ACHIEVED
            ),
            PlanEvaluationDecision.CANCELLED: (
                PlanningAgentLoopStatus.CANCELLED
            ),
            PlanEvaluationDecision.HUMAN_REVIEW_REQUIRED: (
                PlanningAgentLoopStatus
                .HUMAN_REVIEW_REQUIRED
            ),
            PlanEvaluationDecision.TERMINAL_FAILURE: (
                PlanningAgentLoopStatus.FAILED
            ),
        }

        return status_map.get(decision)

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
        """Emit one loop event when tracing is enabled."""

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
        run_status,
        plan_id: str,
        attempt_number: int,
        cycle_count: int,
    ) -> None:
        """Emit one replacement-plan run outcome."""

        from app.schemas.plan_run import PlanRunStatus

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

    @classmethod
    def _emit_terminal(
        cls,
        *,
        trace_session: AgentTraceSession | None,
        status: PlanningAgentLoopStatus,
        plan_id: str,
        attempt_number: int,
    ) -> None:
        """Emit the final agent event for a terminal outcome."""

        event_types = {
            PlanningAgentLoopStatus.GOAL_ACHIEVED: (
                AgentTraceEventType.AGENT_COMPLETED
            ),
            PlanningAgentLoopStatus.CANCELLED: (
                AgentTraceEventType.AGENT_FAILED
            ),
            PlanningAgentLoopStatus.HUMAN_REVIEW_REQUIRED: (
                AgentTraceEventType.AGENT_FAILED
            ),
            PlanningAgentLoopStatus.FAILED: (
                AgentTraceEventType.AGENT_FAILED
            ),
        }

        cls._emit(
            trace_session=trace_session,
            event_type=event_types[status],
            message=f"Planning agent ended: {status.value}.",
            plan_id=plan_id,
            attempt_number=attempt_number,
            metadata={"loop_status": status.value},
        )
