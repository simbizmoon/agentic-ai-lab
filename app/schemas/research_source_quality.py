"""Schemas for deterministic research source quality evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


class ResearchSourceQualityLevel(StrEnum):
    """Overall quality classification for a source."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCELLENT = "excellent"


class ResearchSourceQualityEvaluation(BaseModel):
    """Structured quality assessment for one source document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    document: ResearchSourceDocument
    evaluator: str
    authority_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    primary_source_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    recency_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    completeness_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    traceability_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    overall_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    quality_level: ResearchSourceQualityLevel
    strengths: list[str] = Field(
        default_factory=list
    )
    limitations: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        """Validate evaluation state and descriptive fields."""

        if (
            self.document.status
            is not ResearchSourceDocumentStatus.READ
        ):
            raise ValueError(
                "source quality evaluation requires "
                "a successfully read document"
            )

        if not self.evaluator.strip():
            raise ValueError(
                "evaluator must not be blank"
            )

        self._validate_text_list(
            values=self.strengths,
            field_name="strengths",
        )
        self._validate_text_list(
            values=self.limitations,
            field_name="limitations",
        )

        expected_level = self.level_for_score(
            self.overall_score
        )

        if self.quality_level is not expected_level:
            raise ValueError(
                "quality_level must match overall_score"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @staticmethod
    def _validate_text_list(
        *,
        values: list[str],
        field_name: str,
    ) -> None:
        """Validate nonblank and unique descriptive values."""

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} must not contain "
                "blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain "
                "duplicates"
            )

    @staticmethod
    def level_for_score(
        score: float,
    ) -> ResearchSourceQualityLevel:
        """Return the quality level for one score."""

        if score >= 0.85:
            return ResearchSourceQualityLevel.EXCELLENT

        if score >= 0.70:
            return ResearchSourceQualityLevel.HIGH

        if score >= 0.45:
            return ResearchSourceQualityLevel.MEDIUM

        return ResearchSourceQualityLevel.LOW
