"""Schemas for deterministic plan-step scheduling."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanScheduleReason(StrEnum):
    """Reason describing a scheduling result."""

    STEPS_SELECTED = "steps_selected"
    PLAN_NOT_IN_PROGRESS = "plan_not_in_progress"
    ACTIVE_STEP_EXISTS = "active_step_exists"
    NO_READY_STEPS = "no_ready_steps"
    PLAN_INVALID = "plan_invalid"


class PlanScheduleRequest(BaseModel):
    """Options controlling one scheduling decision."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    allow_parallel_steps: bool = True
    maximum_selected_steps: int = Field(
        default=1,
        ge=1,
        le=100,
    )
    allow_new_steps_while_active: bool = False


class PlanScheduleResult(BaseModel):
    """Deterministic result of selecting executable steps."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    selected_step_ids: list[str] = Field(
        default_factory=list
    )
    ready_step_ids: list[str] = Field(
        default_factory=list
    )
    active_step_ids: list[str] = Field(
        default_factory=list
    )
    reason: PlanScheduleReason

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanScheduleResult:
        """Validate scheduling-result consistency."""

        self._validate_unique_ids(
            values=self.selected_step_ids,
            field_name="selected step IDs",
        )
        self._validate_unique_ids(
            values=self.ready_step_ids,
            field_name="ready step IDs",
        )
        self._validate_unique_ids(
            values=self.active_step_ids,
            field_name="active step IDs",
        )

        if not set(self.selected_step_ids).issubset(
            self.ready_step_ids
        ):
            raise ValueError(
                "selected step IDs must be ready"
            )

        if (
            self.reason
            is PlanScheduleReason.STEPS_SELECTED
            and not self.selected_step_ids
        ):
            raise ValueError(
                "steps_selected requires selected steps"
            )

        if (
            self.reason
            is not PlanScheduleReason.STEPS_SELECTED
            and self.selected_step_ids
        ):
            raise ValueError(
                "non-selection reason must not "
                "contain selected steps"
            )

        return self

    @staticmethod
    def _validate_unique_ids(
        *,
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate nonblank unique step identifiers."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blanks"
            )

        if len(values) != len(set(values)):
            raise ValueError(
                f"{field_name} must be unique"
            )
