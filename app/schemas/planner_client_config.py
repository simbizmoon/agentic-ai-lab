"""Configuration for OpenAI structured planner clients."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PlannerClientConfig(BaseModel):
    """Runtime configuration for one planner-model call."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    model: str = "gpt-5-mini"
    max_output_tokens: int = Field(
        default=4_000,
        ge=100,
        le=100_000,
    )
    reasoning_effort: str | None = "low"
    store: bool = False

    @model_validator(mode="after")
    def validate_config(
        self,
    ) -> PlannerClientConfig:
        """Validate model and reasoning configuration."""

        if not self.model.strip():
            raise ValueError(
                "planner model must not be blank"
            )

        if (
            self.reasoning_effort is not None
            and not self.reasoning_effort.strip()
        ):
            raise ValueError(
                "reasoning_effort must not be blank"
            )

        return self
