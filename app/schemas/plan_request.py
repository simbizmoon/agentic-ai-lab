"""Schemas for requesting structured agent plans."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlanCreationRequest(BaseModel):
    """User goal and constraints supplied to a planner."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    goal: str
    constraints: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    maximum_steps: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    require_tool_for_each_step: bool = False
    allow_parallel_steps: bool = True
    metadata: dict[str, object] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> PlanCreationRequest:
        """Validate goal, constraints, and tool names."""

        if not self.goal.strip():
            raise ValueError(
                "plan goal must not be blank"
            )

        self._validate_unique_text_values(
            values=self.constraints,
            field_name="constraints",
        )
        self._validate_unique_text_values(
            values=self.available_tools,
            field_name="available_tools",
        )

        return self

    @staticmethod
    def _validate_unique_text_values(
        *,
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate one list of case-insensitive text values."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                f"{field_name} must be unique"
            )
