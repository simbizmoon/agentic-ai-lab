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
from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
)
from app.schemas.planning_agent_loop import (
    PlanningAgentAttempt,
    PlanningAgentLoopRequest,
    PlanningAgentLoopResult,
    PlanningAgentLoopStatus,
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

    def run(
        self,
        request: PlanningAgentLoopRequest,
    ) -> PlanningAgentLoopResult:
        """Run initial planning and bounded replanning."""

        try:
            initial_result = self._pipeline.run(
                request.initial
            )
        except PlanningAgentPipelineError as exc:
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
            return PlanningAgentLoopResult(
                attempts=attempts,
                status=terminal_status,
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
                raise PlanningAgentLoopError(
                    "replacement planning failed"
                ) from exc

            lifecycle_result = (
                self._pipeline
                .plan_runner
                .execution_service
                .lifecycle
                .start_plan(
                    planning_result.created_plan.plan
                )
            )

            run_result = self._pipeline.plan_runner.run(
                plan=lifecycle_result.plan,
                request=request.initial.execution,
            )
            evaluation = (
                self._pipeline.plan_evaluator.evaluate(
                    run_result
                )
            )

            attempts.append(
                PlanningAgentAttempt(
                    attempt_number=replan_index + 2,
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
                return PlanningAgentLoopResult(
                    attempts=attempts,
                    status=terminal_status,
                )

        return PlanningAgentLoopResult(
            attempts=attempts,
            status=(
                PlanningAgentLoopStatus
                .REPLAN_LIMIT_REACHED
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
