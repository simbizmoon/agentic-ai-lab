"""Schemas for semantic evidence relevance judgments."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceRelevanceLevel(StrEnum):
    """Categorical relevance of one evidence passage."""

    DIRECTLY_RELEVANT = "directly_relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    IRRELEVANT = "irrelevant"


class EvidenceRelevanceJudgment(BaseModel):
    """Semantic relevance judgment for one evidence passage."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    relevance_level: EvidenceRelevanceLevel
    relevance_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    issues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_judgment(self) -> Self:
        """Validate judgment text and diagnostic consistency."""

        if not self.rationale.strip():
            raise ValueError("rationale must not be blank")

        normalized_issues = [issue.strip() for issue in self.issues]

        if any(not issue for issue in normalized_issues):
            raise ValueError("issues must not contain blank values")

        folded_issues = [issue.casefold() for issue in normalized_issues]
        if len(set(folded_issues)) != len(folded_issues):
            raise ValueError("issues must be unique")

        if (
            self.relevance_level
            is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
            and self.relevance_score == 0.0
        ):
            raise ValueError(
                "directly_relevant must not have zero relevance_score"
            )

        if (
            self.relevance_level
            is EvidenceRelevanceLevel.IRRELEVANT
            and self.relevance_score == 1.0
        ):
            raise ValueError(
                "irrelevant must not have maximum relevance_score"
            )

        return self
