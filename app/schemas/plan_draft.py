"""Schemas for unmaterialized agent plan steps."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanStepDraft(BaseModel):
    """Planner-supplied values for one new plan step."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    step_id: str
    title: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    expected_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_draft(self) -> PlanStepDraft:
        """Validate step text and dependency identifiers."""

        required_text = {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        optional_text = {
            "tool_name": self.tool_name,
            "expected_output": self.expected_output,
        }

        for name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
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

        if self.step_id in self.dependencies:
            raise ValueError(
                "a step must not depend on itself"
            )

        return self
