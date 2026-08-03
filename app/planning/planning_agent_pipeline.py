"""Integrated planning, execution, and evaluation pipeline."""

from __future__ import annotations

from app.planning.plan_evaluator import PlanEvaluator
from app.planning.plan_runner import PlanRunner
from app.planning.planning_service import (
    PlanningService,
    PlanningServiceError,
)
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)
from app.schemas.planning_agent_result import (
    PlanningAgentResult,
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
    ) -> PlanningAgentResult:
        """Plan, execute, and evaluate one request."""

        try:
            planning_result = (
                self.planning_service.create_plan(
                    request.planning
                )
            )
        except PlanningServiceError as exc:
            raise PlanningAgentPipelineError(
                "planning stage failed"
            ) from exc

        lifecycle_result = (
            self.plan_runner
            .execution_service
            .lifecycle
            .start_plan(
                planning_result.created_plan.plan
            )
        )

        run_result = self.plan_runner.run(
            plan=lifecycle_result.plan,
            request=request.execution,
        )

        evaluation = self.plan_evaluator.evaluate(
            run_result
        )

        return PlanningAgentResult(
            planning=planning_result,
            run=run_result,
            evaluation=evaluation,
        )
