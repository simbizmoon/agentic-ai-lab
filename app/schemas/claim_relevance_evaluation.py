"""Schemas for claim relevance evaluation datasets and runs."""

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


class ClaimRelevanceEvaluationCase(BaseModel):
    """One golden request-to-claim relevance evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    question: str
    objective: str
    claim: str
    expected_relevance_level: ClaimRelevanceLevel
    description: str

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        """Validate required case text."""

        required = {
            "case_id": self.case_id,
            "question": self.question,
            "objective": self.objective,
            "claim": self.claim,
            "description": self.description,
        }

        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ClaimRelevanceEvaluationDataset(BaseModel):
    """Golden dataset for claim relevance evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dataset_id: str
    version: str
    cases: list[
        ClaimRelevanceEvaluationCase
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Validate dataset identity and case uniqueness."""

        if not self.dataset_id.strip():
            raise ValueError(
                "dataset_id must not be blank"
            )

        if not self.version.strip():
            raise ValueError(
                "version must not be blank"
            )

        case_ids = [
            case.case_id.strip().casefold()
            for case in self.cases
        ]

        if len(set(case_ids)) != len(case_ids):
            raise ValueError(
                "dataset cases must have unique case IDs"
            )

        return self


class ClaimRelevanceEvaluationCaseResult(BaseModel):
    """Evaluation result for one golden relevance case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    expected_relevance_level: ClaimRelevanceLevel
    actual_relevance_level: ClaimRelevanceLevel
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    correct: bool
    rationale: str
    issues: list[str] = Field(default_factory=list)


class ClaimRelevanceConfusionEntry(BaseModel):
    """One expected-to-actual relevance confusion count."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    expected: ClaimRelevanceLevel
    actual: ClaimRelevanceLevel
    count: int = Field(ge=0)


class ClaimRelevanceEvaluationRun(BaseModel):
    """Aggregate claim relevance evaluation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dataset_id: str
    dataset_version: str
    model: str

    case_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    accuracy: float = Field(
        ge=0.0,
        le=1.0,
    )

    false_directly_relevant_count: int = Field(ge=0)
    false_irrelevant_count: int = Field(ge=0)

    results: list[
        ClaimRelevanceEvaluationCaseResult
    ] = Field(default_factory=list)

    confusion: list[
        ClaimRelevanceConfusionEntry
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_run(self) -> Self:
        """Validate aggregate evaluation metrics."""

        if self.case_count != len(self.results):
            raise ValueError(
                "case_count must match results length"
            )

        actual_correct_count = sum(
            result.correct
            for result in self.results
        )

        if self.correct_count != actual_correct_count:
            raise ValueError(
                "correct_count must match correct results"
            )

        expected_accuracy = (
            actual_correct_count / self.case_count
            if self.case_count
            else 0.0
        )

        if abs(self.accuracy - expected_accuracy) > 1e-12:
            raise ValueError(
                "accuracy must match evaluation results"
            )

        confusion_count = sum(
            entry.count
            for entry in self.confusion
        )

        if confusion_count != self.case_count:
            raise ValueError(
                "confusion counts must match case_count"
            )

        return self
