"""Schemas for semantic answer coverage judgments."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnswerCoverageLevel(StrEnum):
    """Categorical coverage of one final claim set."""

    FULLY_COVERED = "fully_covered"
    PARTIALLY_COVERED = "partially_covered"
    INSUFFICIENT = "insufficient"


class AnswerCoverageJudgment(BaseModel):
    """Semantic coverage judgment for one research answer."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    coverage_level: AnswerCoverageLevel
    coverage_score: float = Field(ge=0.0, le=1.0)
    covered_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    rationale: str

    @model_validator(mode="after")
    def validate_judgment(self) -> Self:
        """Validate diagnostic text and categorical consistency."""

        if not self.rationale.strip():
            raise ValueError("rationale must not be blank")

        self._validate_unique_text(
            self.covered_aspects,
            field_name="covered_aspects",
        )
        self._validate_unique_text(
            self.missing_aspects,
            field_name="missing_aspects",
        )

        if (
            self.coverage_level is AnswerCoverageLevel.FULLY_COVERED
            and self.missing_aspects
        ):
            raise ValueError(
                "fully_covered must not include missing_aspects"
            )

        if (
            self.coverage_level is AnswerCoverageLevel.INSUFFICIENT
            and self.coverage_score == 1.0
        ):
            raise ValueError(
                "insufficient must not have maximum coverage_score"
            )

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        normalized = [value.strip() for value in values]

        if any(not value for value in normalized):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        folded = [value.casefold() for value in normalized]
        if len(set(folded)) != len(folded):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )
