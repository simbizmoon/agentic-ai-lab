"""Creation of replacement plans from structured replan context."""

from __future__ import annotations

from app.planning.plan_factory import (
    PlanFactory,
    PlanFactoryError,
)
from app.planning.planner_client import (
    PlannerClient,
    PlannerClientError,
)
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planning_result import PlanningResult
from app.schemas.replan import ReplanRequest


class ReplanningServiceError(RuntimeError):
    """Raised when replacement-plan creation fails."""


class ReplanningService:
    """Generate and materialize one replacement plan."""

    def __init__(
        self,
        *,
        prompt_composer: PlannerPromptComposer,
        planner_client: PlannerClient,
        plan_factory: PlanFactory,
    ) -> None:
        self._prompt_composer = prompt_composer
        self._planner_client = planner_client
        self._plan_factory = plan_factory

    @property
    def prompt_composer(
        self,
    ) -> PlannerPromptComposer:
        """Return the configured prompt composer."""

        return self._prompt_composer

    @property
    def planner_client(
        self,
    ) -> PlannerClient:
        """Return the configured planner client."""

        return self._planner_client

    @property
    def plan_factory(
        self,
    ) -> PlanFactory:
        """Return the configured plan factory."""

        return self._plan_factory

    def create_plan(
        self,
        request: ReplanRequest,
    ) -> PlanningResult:
        """Create one validated replacement plan."""

        policy_request = self._policy_request(request)
        prompt = self.prompt_composer.compose_replan(
            request
        )

        try:
            planner_result = (
                self.planner_client.create_plan(
                    request=policy_request,
                    prompt=prompt,
                )
            )
        except PlannerClientError as exc:
            raise ReplanningServiceError(
                "planner client failed during replanning"
            ) from exc

        if not planner_result.validation.valid:
            issue_codes = [
                issue.code.value
                for issue
                in planner_result.validation.issues
            ]

            raise ReplanningServiceError(
                "replanner output failed policy validation: "
                + ", ".join(issue_codes)
            )

        try:
            created_plan = self.plan_factory.create(
                request=policy_request,
                steps=list(
                    planner_result.output.steps
                ),
            )
        except PlanFactoryError as exc:
            raise ReplanningServiceError(
                "replanner output could not be materialized"
            ) from exc

        if not created_plan.validation.valid:
            raise ReplanningServiceError(
                "replacement plan failed validation"
            )

        return PlanningResult(
            prompt=prompt,
            planner_result=planner_result,
            created_plan=created_plan,
        )

    @staticmethod
    def _policy_request(
        request: ReplanRequest,
    ) -> PlanCreationRequest:
        """Convert replan context into planner policy options."""

        return PlanCreationRequest(
            goal=request.goal,
            constraints=list(request.constraints),
            available_tools=list(request.available_tools),
            maximum_steps=request.maximum_steps,
            allow_parallel_steps=True,
            require_tool_for_each_step=False,
            metadata={
                "source_plan_id": request.original_plan_id,
                "replanning": True,
            },
        )
