"""Schemas returned after materializing an agent plan."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.plan import Plan
from app.schemas.plan_validation import (
    PlanValidationResult,
)


class CreatedPlan(BaseModel):
    """Materialized plan and its initial validation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    plan: Plan
    validation: PlanValidationResult

    @model_validator(mode="after")
    def validate_created_plan(
        self,
    ) -> CreatedPlan:
        """Validate Plan and validation-result consistency."""

        plan_step_ids = {
            step.step_id
            for step in self.plan.steps
        }
        execution_step_ids = set(
            self.validation.execution_order
        )

        if (
            self.validation.valid
            and execution_step_ids != plan_step_ids
        ):
            raise ValueError(
                "valid plan execution order must contain "
                "all plan steps"
            )

        if (
            not self.validation.valid
            and self.validation.execution_order
            and not execution_step_ids.issubset(
                plan_step_ids
            )
        ):
            raise ValueError(
                "execution order contains unknown plan steps"
            )

        return self
