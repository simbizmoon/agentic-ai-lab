"""Schemas for end-to-end agent plan execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan import Plan
from app.schemas.plan_schedule import PlanScheduleResult
from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
)
from app.schemas.plan_validation import (
    PlanValidationResult,
)


class PlanExecutionStatus(StrEnum):
    """Outcome states for one plan execution cycle."""

    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    NOTHING_SCHEDULED = "nothing_scheduled"


class PlanExecutionResult(BaseModel):
    """Result of one scheduler-executor lifecycle cycle."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    plan: Plan
    validation: PlanValidationResult
    schedule: PlanScheduleResult
    step_results: list[PlanStepExecutionResult] = Field(
        default_factory=list
    )
    status: PlanExecutionStatus

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanExecutionResult:
        """Validate execution-result consistency."""

        step_ids = [
            result.step_id
            for result in self.step_results
        ]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError(
                "step execution results must have unique step IDs"
            )

        if (
            self.status
            is PlanExecutionStatus.NOTHING_SCHEDULED
            and self.step_results
        ):
            raise ValueError(
                "nothing_scheduled must not contain step results"
            )

        if (
            self.status
            is not PlanExecutionStatus.NOTHING_SCHEDULED
            and not self.step_results
        ):
            raise ValueError(
                "step execution status requires step results"
            )

        return self
