"""Configuration for building agent memory context."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class MemoryContextConfig(BaseModel):
    """Limits used while building prompt memory context."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    maximum_items: int = Field(
        default=5,
        ge=1,
        le=50,
    )
    maximum_content_characters: int = Field(
        default=800,
        ge=50,
        le=10_000,
    )
    minimum_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
    )
    include_tags: bool = True
    include_source_reference: bool = True

    @model_validator(mode="after")
    def validate_config(
        self,
    ) -> MemoryContextConfig:
        """Validate context limits."""

        if (
            self.maximum_content_characters
            < 50
        ):
            raise ValueError(
                "maximum_content_characters is too small"
            )

        return self
