"""Schemas for deterministic agent-plan validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanValidationSeverity(StrEnum):
    """Severity levels for plan validation issues."""

    ERROR = "error"
    WARNING = "warning"


class PlanValidationCode(StrEnum):
    """Stable codes for plan validation findings."""

    CIRCULAR_DEPENDENCY = "circular_dependency"
    DEPENDENCY_ORDER_VIOLATION = (
        "dependency_order_violation"
    )
    READY_WITH_INCOMPLETE_DEPENDENCY = (
        "ready_with_incomplete_dependency"
    )
    PENDING_WITH_COMPLETED_DEPENDENCIES = (
        "pending_with_completed_dependencies"
    )
    DEPENDS_ON_FAILED_STEP = "depends_on_failed_step"
    TERMINAL_PLAN_HAS_ACTIVE_STEPS = (
        "terminal_plan_has_active_steps"
    )
    COMPLETED_PLAN_HAS_INCOMPLETE_STEPS = (
        "completed_plan_has_incomplete_steps"
    )
    FAILED_PLAN_HAS_NO_FAILED_STEP = (
        "failed_plan_has_no_failed_step"
    )


class PlanValidationIssue(BaseModel):
    """One deterministic plan validation finding."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    code: PlanValidationCode
    severity: PlanValidationSeverity
    message: str
    step_id: str | None = None
    related_step_ids: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_issue(
        self,
    ) -> PlanValidationIssue:
        """Validate issue text and identifiers."""

        if not self.message.strip():
            raise ValueError(
                "validation issue message must not be blank"
            )

        if (
            self.step_id is not None
            and not self.step_id.strip()
        ):
            raise ValueError(
                "validation issue step_id must not be blank"
            )

        if any(
            not step_id.strip()
            for step_id in self.related_step_ids
        ):
            raise ValueError(
                "related step IDs must not be blank"
            )

        if len(self.related_step_ids) != len(
            set(self.related_step_ids)
        ):
            raise ValueError(
                "related step IDs must be unique"
            )

        return self


class PlanValidationResult(BaseModel):
    """Complete validation result for one plan."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    valid: bool
    issues: list[PlanValidationIssue] = Field(
        default_factory=list
    )
    execution_order: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanValidationResult:
        """Validate result consistency."""

        has_errors = any(
            issue.severity
            is PlanValidationSeverity.ERROR
            for issue in self.issues
        )

        if self.valid == has_errors:
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
