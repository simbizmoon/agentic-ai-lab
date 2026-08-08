"""Production schema for claim relevance evaluation results."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


class ResearchClaimRelevanceEvaluation(BaseModel):
    """Recorded relevance evaluation for one research claim."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    claim_id: str
    relevance_level: ClaimRelevanceLevel
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    rationale: str
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evaluation(
        self,
    ) -> Self:
        """Validate identifiers and diagnostic text."""

        required_text = {
            "evaluation_id": self.evaluation_id,
            "claim_id": self.claim_id,
            "rationale": self.rationale,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        for issue in self.issues:
            if not issue.strip():
                raise ValueError(
                    "issues must not contain blank values"
                )

        normalized_issues = [
            issue.strip().casefold()
            for issue in self.issues
        ]

        if len(set(normalized_issues)) != len(
            normalized_issues
        ):
            raise ValueError(
                "issues must not contain duplicates"
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
