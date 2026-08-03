"""Schemas for deterministic agent-plan replanning context."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
)


class ReplanStepSummary(BaseModel):
    """Relevant execution information about one previous step."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    step_id: str
    title: str
    description: str
    status: str
    tool_name: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    output: Any | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_summary(self) -> ReplanStepSummary:
        """Validate step summary text and identifiers."""

        required_text = {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if (
            self.tool_name is not None
            and not self.tool_name.strip()
        ):
            raise ValueError(
                "tool_name must not be blank"
            )

        if (
            self.error_message is not None
            and not self.error_message.strip()
        ):
            raise ValueError(
                "error_message must not be blank"
            )

        if any(
            not dependency.strip()
            for dependency in self.dependencies
        ):
            raise ValueError(
                "dependencies must not contain blank IDs"
            )

        if len(self.dependencies) != len(
            set(self.dependencies)
        ):
            raise ValueError(
                "dependencies must be unique"
            )

        return self


class ReplanRequest(BaseModel):
    """Structured context supplied to a future replanner."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    original_plan_id: str
    goal: str
    evaluation_decision: PlanEvaluationDecision
    evaluation_codes: list[PlanEvaluationCode] = Field(
        min_length=1
    )
    evaluation_summary: str
    completed_steps: list[ReplanStepSummary] = Field(
        default_factory=list
    )
    failed_steps: list[ReplanStepSummary] = Field(
        default_factory=list
    )
    incomplete_steps: list[ReplanStepSummary] = Field(
        default_factory=list
    )
    constraints: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    maximum_steps: int = Field(default=10, ge=1, le=100)
    previous_cycle_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> ReplanRequest:
        """Validate replanning context consistency."""

        required_text = {
            "original_plan_id": self.original_plan_id,
            "goal": self.goal,
            "evaluation_summary": self.evaluation_summary,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if len(self.evaluation_codes) != len(
            set(self.evaluation_codes)
        ):
            raise ValueError(
                "evaluation codes must be unique"
            )

        self._validate_unique_text(
            self.constraints,
            "constraints",
        )
        self._validate_unique_text(
            self.available_tools,
            "available_tools",
        )

        all_step_ids = [
            step.step_id
            for values in (
                self.completed_steps,
                self.failed_steps,
                self.incomplete_steps,
            )
            for step in values
        ]

        if len(all_step_ids) != len(set(all_step_ids)):
            raise ValueError(
                "step summaries must not overlap"
            )

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate nonblank case-insensitive unique values."""

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
