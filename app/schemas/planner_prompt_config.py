"""Configuration for planner prompt composition."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlannerPromptConfig(BaseModel):
    """Options controlling planner prompt rendering."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    include_metadata: bool = False
    include_previous_outputs: bool = True
    maximum_output_characters: int = Field(
        default=2_000,
        ge=100,
        le=100_000,
    )
