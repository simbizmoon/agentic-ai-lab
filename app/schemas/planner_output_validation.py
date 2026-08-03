"""Schemas for deterministic validation of planner output."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlannerOutputValidationCode(StrEnum):
    """Stable validation codes for planner output."""

    TOO_MANY_STEPS = "too_many_steps"
    TOOL_REQUIRED = "tool_required"
    TOOL_NOT_AVAILABLE = "tool_not_available"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    PARALLEL_STEPS_NOT_ALLOWED = (
        "parallel_steps_not_allowed"
    )


class PlannerOutputValidationIssue(BaseModel):
    """One deterministic planner-output validation issue."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    code: PlannerOutputValidationCode
    message: str
    step_id: str | None = None
    related_step_ids: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_issue(
        self,
    ) -> PlannerOutputValidationIssue:
        """Validate issue text and identifiers."""

        if not self.message.strip():
            raise ValueError(
                "planner validation message must not be blank"
            )

        if (
            self.step_id is not None
            and not self.step_id.strip()
        ):
            raise ValueError(
                "planner validation step_id must not be blank"
            )

        if any(
            not step_id.strip()
            for step_id in self.related_step_ids
        ):
            raise ValueError(
                "related step IDs must not contain blanks"
            )

        if len(self.related_step_ids) != len(
            set(self.related_step_ids)
        ):
            raise ValueError(
                "related step IDs must be unique"
            )

        return self


class PlannerOutputValidationResult(BaseModel):
    """Complete deterministic validation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    valid: bool
    issues: list[PlannerOutputValidationIssue] = Field(
        default_factory=list
    )
    execution_order: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlannerOutputValidationResult:
        """Validate result consistency."""

        if self.valid == bool(self.issues):
            raise ValueError(
                "valid flag is inconsistent with issues"
            )

        if len(self.execution_order) != len(
            set(self.execution_order)
        ):
            raise ValueError(
                "execution order must contain unique step IDs"
            )

        return self
