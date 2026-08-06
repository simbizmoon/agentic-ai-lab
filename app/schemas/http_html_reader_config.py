"""Configuration for the HTTP/HTML research source reader."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HttpHtmlReaderConfig(BaseModel):
    """Validated safety limits for live source reading."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    maximum_bytes: int = Field(
        default=1_000_000,
        ge=1_024,
        le=10_000_000,
    )
    maximum_redirects: int = Field(default=3, ge=0, le=10)
    user_agent: str = "AIRA-ResearchReader/0.1"

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        """Validate reader configuration."""

        if not self.user_agent.strip():
            raise ValueError("user_agent must not be blank")

        return self
