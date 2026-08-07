"""Schemas for semantic citation evaluation datasets and runs."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


class SemanticCitationEvaluationCase(BaseModel):
    """One golden claim-to-evidence semantic evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    claim: str
    evidence: str
    expected_support_level: SemanticCitationSupportLevel
    description: str

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        """Validate required case text."""

        required = {
            "case_id": self.case_id,
            "claim": self.claim,
            "evidence": self.evidence,
            "description": self.description,
        }

        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class SemanticCitationEvaluationDataset(BaseModel):
    """Golden dataset for semantic citation verification."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dataset_id: str
    version: str
    cases: list[
        SemanticCitationEvaluationCase
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


class SemanticCitationEvaluationCaseResult(BaseModel):
    """Evaluation result for one golden case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    expected_support_level: SemanticCitationSupportLevel
    actual_support_level: SemanticCitationSupportLevel
    entailment_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    correct: bool
    rationale: str
    issues: list[str] = Field(default_factory=list)


class SemanticCitationConfusionEntry(BaseModel):
    """One expected-to-actual confusion count."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    expected: SemanticCitationSupportLevel
    actual: SemanticCitationSupportLevel
    count: int = Field(ge=0)


class SemanticCitationEvaluationRun(BaseModel):
    """Aggregate semantic citation evaluation result."""

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

    false_fully_supported_count: int = Field(ge=0)
    false_rejected_count: int = Field(ge=0)

    results: list[
        SemanticCitationEvaluationCaseResult
    ] = Field(default_factory=list)

    confusion: list[
        SemanticCitationConfusionEntry
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
