"""Structured judgment for claim relevance to a research request."""

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


class ClaimRelevanceLevel(StrEnum):
    """Categorical relevance of one claim to the research request."""

    DIRECTLY_RELEVANT = "directly_relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    IRRELEVANT = "irrelevant"


class ClaimRelevanceJudgment(BaseModel):
    """Structured semantic relevance judgment for one research claim."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    relevance_level: ClaimRelevanceLevel
    relevance_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    issues: list[str] = Field(default_factory=list)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        """Reject blank rationale text."""

        if not value.strip():
            raise ValueError("rationale must not be blank")
        return value

    @field_validator("issues")
    @classmethod
    def validate_issues(cls, values: list[str]) -> list[str]:
        """Reject blank issue descriptions."""

        if any(not value.strip() for value in values):
            raise ValueError("issues must not contain blank values")
        return values

    @model_validator(mode="after")
    def validate_level_score_consistency(self) -> Self:
        """Keep score diagnostic without turning it into policy."""

        if (
            self.relevance_level
            is ClaimRelevanceLevel.DIRECTLY_RELEVANT
            and self.relevance_score == 0.0
        ):
            raise ValueError(
                "directly_relevant must not have zero relevance_score"
            )

        if (
            self.relevance_level
            is ClaimRelevanceLevel.IRRELEVANT
            and self.relevance_score == 1.0
        ):
            raise ValueError(
                "irrelevant must not have maximum relevance_score"
            )

        return self


class ClaimRelevanceBatchItemJudgment(BaseModel):
    """One identified claim relevance judgment in a batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    item_id: str
    judgment: ClaimRelevanceJudgment

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        """Reject blank local item identity."""

        if not value.strip():
            raise ValueError("item_id must not be blank")
        return value


class ClaimRelevanceBatchJudgment(BaseModel):
    """Structured relevance judgments for one local claim batch."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[ClaimRelevanceBatchItemJudgment] = Field(min_length=1)

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
