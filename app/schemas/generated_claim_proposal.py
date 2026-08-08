"""Structured proposal returned by a generative claim model."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
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


class GeneratedClaimProposalBatchItem(BaseModel):
    """One identified generated claim proposal in a batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    item_id: str
    proposal: GeneratedClaimProposal

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        """Reject blank local batch identity."""

        if not value.strip():
            raise ValueError("item_id must not be blank")
        return value


class GeneratedClaimProposalBatch(BaseModel):
    """Structured claim proposals for one evidence batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[GeneratedClaimProposalBatchItem] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        """Require unique local item identities."""

        normalized_ids = [
            item.item_id.strip().casefold()
            for item in self.items
        ]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("batch item IDs must be unique")
        return self
