"""Production schema for answer coverage evaluation results."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


class ResearchAnswerCoverageEvaluation(BaseModel):
    """Recorded semantic coverage evaluation for one research claim set."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    request_id: str
    claim_ids: list[str] = Field(min_length=1)
    coverage_level: AnswerCoverageLevel
    coverage_score: float = Field(ge=0.0, le=1.0)
    covered_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    rationale: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        """Validate identifiers and diagnostic text."""

        required_text = {
            "evaluation_id": self.evaluation_id,
            "request_id": self.request_id,
            "rationale": self.rationale,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        normalized_claim_ids = [
            claim_id.strip()
            for claim_id in self.claim_ids
        ]

        if any(not claim_id for claim_id in normalized_claim_ids):
            raise ValueError(
                "claim_ids must not contain blank values"
            )

        folded_claim_ids = [
            claim_id.casefold()
            for claim_id in normalized_claim_ids
        ]
        if len(set(folded_claim_ids)) != len(folded_claim_ids):
            raise ValueError(
                "claim_ids must not contain duplicates"
            )

        self._validate_unique_text(
            self.covered_aspects,
            field_name="covered_aspects",
        )
        self._validate_unique_text(
            self.missing_aspects,
            field_name="missing_aspects",
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
