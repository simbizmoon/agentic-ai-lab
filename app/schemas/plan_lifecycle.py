"""Schemas returned by agent plan lifecycle operations."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan import Plan
from app.schemas.plan_validation import (
    PlanValidationResult,
)


class PlanLifecycleResult(BaseModel):
    """Updated plan and validation after a lifecycle operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    plan: Plan
    validation: PlanValidationResult
    changed_step_ids: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanLifecycleResult:
        """Validate changed step identifiers."""

        if len(self.changed_step_ids) != len(
            set(self.changed_step_ids)
        ):
            raise ValueError(
                "changed step IDs must be unique"
            )

        known_step_ids = {
            step.step_id
            for step in self.plan.steps
        }

        unknown_step_ids = (
            set(self.changed_step_ids)
            - known_step_ids
        )

        if unknown_step_ids:
            raise ValueError(
                "changed step IDs must reference "
                "steps in the plan"
            )

        return self
