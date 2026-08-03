"""Schemas for deterministic evaluation of agent plan runs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanEvaluationDecision(StrEnum):
    """Decision produced after evaluating a plan run."""

    GOAL_ACHIEVED = "goal_achieved"
    CONTINUE = "continue"
    REPLAN_REQUIRED = "replan_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    TERMINAL_FAILURE = "terminal_failure"
    CANCELLED = "cancelled"


class PlanEvaluationCode(StrEnum):
    """Stable reason codes for plan evaluation."""

    PLAN_COMPLETED = "plan_completed"
    PLAN_CANCELLED = "plan_cancelled"
    STEP_EXECUTION_FAILED = "step_execution_failed"
    PLAN_VALIDATION_FAILED = "plan_validation_failed"
    NO_EXECUTABLE_STEP = "no_executable_step"
    CYCLE_LIMIT_REACHED = "cycle_limit_reached"
    PLAN_STILL_IN_PROGRESS = "plan_still_in_progress"
    PLAN_FAILED_WITHOUT_STEP_ERROR = (
        "plan_failed_without_step_error"
    )


class PlanEvaluationResult(BaseModel):
    """Deterministic evaluation of one completed plan run attempt."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    decision: PlanEvaluationDecision
    codes: list[PlanEvaluationCode] = Field(
        min_length=1
    )
    summary: str
    failed_step_ids: list[str] = Field(
        default_factory=list
    )
    incomplete_step_ids: list[str] = Field(
        default_factory=list
    )
    replan_recommended: bool
    human_review_recommended: bool

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanEvaluationResult:
        """Validate evaluation-result consistency."""

        if not self.summary.strip():
            raise ValueError(
                "evaluation summary must not be blank"
            )

        self._validate_unique_ids(
            values=self.failed_step_ids,
            field_name="failed step IDs",
        )
        self._validate_unique_ids(
            values=self.incomplete_step_ids,
            field_name="incomplete step IDs",
        )

        if len(self.codes) != len(set(self.codes)):
            raise ValueError(
                "evaluation codes must be unique"
            )

        if (
            self.decision
            is PlanEvaluationDecision.REPLAN_REQUIRED
            and not self.replan_recommended
        ):
            raise ValueError(
                "replan_required must recommend replanning"
            )

        if (
            self.decision
            is PlanEvaluationDecision.HUMAN_REVIEW_REQUIRED
            and not self.human_review_recommended
        ):
            raise ValueError(
                "human_review_required must recommend "
                "human review"
            )

        if (
            self.decision
            is PlanEvaluationDecision.GOAL_ACHIEVED
            and (
                self.failed_step_ids
                or self.incomplete_step_ids
                or self.replan_recommended
            )
        ):
            raise ValueError(
                "goal_achieved must not contain unfinished work"
            )

        return self

    @staticmethod
    def _validate_unique_ids(
        *,
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate nonblank unique identifiers."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blanks"
            )

        if len(values) != len(set(values)):
            raise ValueError(
                f"{field_name} must be unique"
            )
