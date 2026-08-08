"""Schemas for model-assisted semantic citation judgment."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SemanticCitationSupportLevel(StrEnum):
    """Semantic relationship between evidence and a claim."""

    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class SemanticCitationJudgment(BaseModel):
    """Semantic support judgment returned by a model."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    support_level: SemanticCitationSupportLevel
    entailment_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    rationale: str
    issues: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_judgment(self) -> Self:
        """Validate rationale and issue text."""

        if not self.rationale.strip():
            raise ValueError(
                "rationale must not be blank"
            )

        if any(
            not issue.strip()
            for issue in self.issues
        ):
            raise ValueError(
                "issues must not contain blank values"
            )

        normalized = [
            issue.strip().casefold()
            for issue in self.issues
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "issues must not contain duplicates"
            )

        return self

class SemanticCitationBatchItemJudgment(BaseModel):
    """One identified semantic citation judgment in a batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    item_id: str
    judgment: SemanticCitationJudgment

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        """Reject blank local batch identity."""

        if not value.strip():
            raise ValueError("item_id must not be blank")
        return value


class SemanticCitationBatchJudgment(BaseModel):
    """Structured citation judgments for one local batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[SemanticCitationBatchItemJudgment] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        """Require unique stable item identities."""

        normalized_ids = [
            item.item_id.strip().casefold()
            for item in self.items
        ]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("batch item IDs must be unique")
        return self
