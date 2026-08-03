"""Schemas for structured output returned by a planner model."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan_draft import PlanStepDraft


class PlanDraftOutput(BaseModel):
    """Structured plan-step output returned by a planner."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    reasoning_summary: str
    steps: list[PlanStepDraft] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_output(self) -> PlanDraftOutput:
        """Validate planner output text and step identifiers."""

        if not self.reasoning_summary.strip():
            raise ValueError(
                "reasoning summary must not be blank"
            )

        self._validate_text_list(
            values=self.assumptions,
            field_name="assumptions",
        )
        self._validate_text_list(
            values=self.warnings,
            field_name="warnings",
        )

        step_ids = [
            step.step_id
            for step in self.steps
        ]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError(
                "planner output step IDs must be unique"
            )

        known_step_ids = set(step_ids)

        for step in self.steps:
            unknown_dependencies = (
                set(step.dependencies)
                - known_step_ids
            )

            if unknown_dependencies:
                raise ValueError(
                    "planner output dependencies must "
                    "reference generated steps"
                )

        return self

    @staticmethod
    def _validate_text_list(
        *,
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate nonblank case-insensitive unique text."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blanks"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                f"{field_name} must be unique"
            )
