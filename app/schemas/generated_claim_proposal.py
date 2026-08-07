"""Structured proposal returned by a generative claim model."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)


class GeneratedClaimProposal(BaseModel):
    """Meaning-only claim proposal derived from one evidence item."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    text: str
    rationale: str

    @model_validator(mode="after")
    def validate_proposal(self) -> Self:
        """Reject blank generated claim content."""

        if not self.text.strip():
            raise ValueError("text must not be blank")

        if not self.rationale.strip():
            raise ValueError("rationale must not be blank")

        return self
