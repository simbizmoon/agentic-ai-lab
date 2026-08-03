"""Integrated creation of validated structured agent plans."""

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


class PlanningServiceError(RuntimeError):
    """Raised when a structured plan cannot be created."""


class PlanningService:
    """Compose, generate, validate, and materialize a plan."""

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
        request: PlanCreationRequest,
    ) -> PlanningResult:
        """Create one validated materialized plan."""

        prompt = self.prompt_composer.compose_initial(
            request
        )

        try:
            planner_result = (
                self.planner_client.create_plan(
                    request=request,
                    prompt=prompt,
                )
            )
        except PlannerClientError as exc:
            raise PlanningServiceError(
                "planner client failed to create output"
            ) from exc

        if not planner_result.validation.valid:
            issue_codes = [
                issue.code.value
                for issue
                in planner_result.validation.issues
            ]

            raise PlanningServiceError(
                "planner output failed policy validation: "
                + ", ".join(issue_codes)
            )

        try:
            created_plan = self.plan_factory.create(
                request=request,
                steps=list(
                    planner_result.output.steps
                ),
            )
        except PlanFactoryError as exc:
            raise PlanningServiceError(
                "validated planner output could not "
                "be materialized"
            ) from exc

        if not created_plan.validation.valid:
            error_codes = [
                issue.code.value
                for issue in created_plan.validation.issues
                if issue.severity.value == "error"
            ]

            raise PlanningServiceError(
                "materialized plan failed validation: "
                + ", ".join(error_codes)
            )

        return PlanningResult(
            prompt=prompt,
            planner_result=planner_result,
            created_plan=created_plan,
        )
