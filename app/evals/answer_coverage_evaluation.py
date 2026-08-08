"""Schemas for semantic answer coverage evaluation datasets and runs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


class AnswerCoverageEvaluationCase(BaseModel):
    """One answer coverage golden-evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    question: str
    objective: str
    claims: list[str] = Field(min_length=1)
    expected_coverage_level: AnswerCoverageLevel


class AnswerCoverageEvaluationDataset(BaseModel):
    """Versioned answer coverage evaluation dataset."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dataset_id: str
    version: str
    cases: list[AnswerCoverageEvaluationCase] = Field(min_length=1)


class AnswerCoverageEvaluationCaseResult(BaseModel):
    """Evaluation output for one answer coverage case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    case_id: str
    expected_coverage_level: AnswerCoverageLevel
    actual_coverage_level: AnswerCoverageLevel
    coverage_score: float = Field(ge=0.0, le=1.0)
    correct: bool
    covered_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    rationale: str


class AnswerCoverageConfusionEntry(BaseModel):
    """One confusion-matrix entry."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    expected: AnswerCoverageLevel
    actual: AnswerCoverageLevel
    count: int = Field(ge=1)


class AnswerCoverageEvaluationRun(BaseModel):
    """Aggregate answer coverage evaluation run."""

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
    accuracy: float = Field(ge=0.0, le=1.0)
    false_fully_covered_count: int = Field(ge=0)
    false_insufficient_count: int = Field(ge=0)
    results: list[AnswerCoverageEvaluationCaseResult] = Field(
        default_factory=list
    )
    confusion: list[AnswerCoverageConfusionEntry] = Field(
        default_factory=list
    )
