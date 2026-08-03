"""Schemas for running structured plans across execution cycles."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan import Plan
from app.schemas.plan_execution import PlanExecutionResult
from app.schemas.plan_schedule import PlanScheduleRequest
from app.schemas.plan_validation import PlanValidationResult


class PlanRunStatus(StrEnum):
    """Terminal outcomes for one plan-run attempt."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    CYCLE_LIMIT_REACHED = "cycle_limit_reached"


class PlanRunRequest(BaseModel):
    """Options controlling repeated plan execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    maximum_cycles: int = Field(
        default=100,
        ge=1,
        le=10_000,
    )
    schedule_request: PlanScheduleRequest = Field(
        default_factory=PlanScheduleRequest
    )
    stop_on_no_progress: bool = True


class PlanRunResult(BaseModel):
    """Result of repeatedly executing a structured plan."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    plan: Plan
    validation: PlanValidationResult
    cycles: list[PlanExecutionResult] = Field(
        default_factory=list
    )
    status: PlanRunStatus
    message: str
    executed_step_ids: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(self) -> PlanRunResult:
        """Validate run-result consistency."""

        if not self.message.strip():
            raise ValueError(
                "plan run message must not be blank"
            )

        if len(self.executed_step_ids) != len(
            set(self.executed_step_ids)
        ):
            raise ValueError(
                "executed step IDs must be unique"
            )

        known_step_ids = {
            step.step_id
            for step in self.plan.steps
        }

        if not set(self.executed_step_ids).issubset(
            known_step_ids
        ):
            raise ValueError(
                "executed step IDs must reference plan steps"
            )

        cycle_step_ids = [
            step_result.step_id
            for cycle in self.cycles
            for step_result in cycle.step_results
        ]

        if self.executed_step_ids != list(
            dict.fromkeys(cycle_step_ids)
        ):
            raise ValueError(
                "executed step IDs must match cycle results"
            )

        return self
