"""Schemas returned by the integrated planning service."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.created_plan import CreatedPlan
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_prompt import PlannerPrompt


class PlanningResult(BaseModel):
    """Prompt, planner output, and materialized plan."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    prompt: PlannerPrompt
    planner_result: PlannerClientResult
    created_plan: CreatedPlan

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanningResult:
        """Validate cross-layer planning consistency."""

        if not self.planner_result.validation.valid:
            raise ValueError(
                "planning result requires valid planner output"
            )

        output_step_ids = [
            step.step_id
            for step in self.planner_result.output.steps
        ]
        plan_step_ids = [
            step.step_id
            for step in self.created_plan.plan.steps
        ]

        if output_step_ids != plan_step_ids:
            raise ValueError(
                "created plan steps must match planner output"
            )

        if (
            self.prompt.maximum_steps
            < len(self.created_plan.plan.steps)
        ):
            raise ValueError(
                "created plan exceeds prompt maximum_steps"
            )

        return self
