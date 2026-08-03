"""Schemas for structured agent plans."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanStatus(StrEnum):
    """Lifecycle states for an agent plan."""

    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStepStatus(StrEnum):
    """Lifecycle states for one plan step."""

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    """One executable or informational step in a plan."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    step_id: str
    title: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    tool_name: str | None = None
    expected_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_step(self) -> PlanStep:
        """Validate identifiers, text, and dependencies."""

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


class Plan(BaseModel):
    """Structured multi-step agent plan."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    plan_id: str
    goal: str
    status: PlanStatus = PlanStatus.DRAFT
    steps: list[PlanStep] = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_plan(self) -> Plan:
        """Validate text, timestamps, and step identifiers."""

        if not self.plan_id.strip():
            raise ValueError(
                "plan_id must not be blank"
            )

        if not self.goal.strip():
            raise ValueError(
                "plan goal must not be blank"
            )

        timestamps = {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        for name, value in timestamps.items():
            if value.tzinfo is None:
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

            if value.utcoffset() != UTC.utcoffset(value):
                raise ValueError(
                    f"{name} must use UTC"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at must not be earlier than created_at"
            )

        step_ids = [
            step.step_id
            for step in self.steps
        ]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError(
                "plan step IDs must be unique"
            )

        known_step_ids = set(step_ids)

        for step in self.steps:
            unknown_dependencies = (
                set(step.dependencies)
                - known_step_ids
            )

            if unknown_dependencies:
                raise ValueError(
                    "step dependencies must reference "
                    "steps in the same plan"
                )

        return self
