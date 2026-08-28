"""Locked contracts for Stage 9 real-research evaluation experiments."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.evals.evaluation_case_definition import EvaluationCaseDefinition
from app.schemas.monetary_cost_budget import MonetaryCostBudget


class Stage9EvaluationDomain(StrEnum):
    GENERAL_TECHNICAL = "general_technical"
    ACADEMIC = "academic"
    PATENT = "patent"
    CROSS_SOURCE = "cross_source"


class Stage9DatasetPartition(StrEnum):
    DEVELOPMENT = "development"
    LOCKED = "locked"


class HumanReviewDimension(StrEnum):
    USEFULNESS = "usefulness"
    CORRECTNESS = "correctness"
    EVIDENCE_GROUNDING = "evidence_grounding"
    UNCERTAINTY_DISCLOSURE = "uncertainty_disclosure"


class Stage9HumanReviewCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    criterion_id: str
    dimension: HumanReviewDimension
    question: str
    minimum_score: int = Field(ge=1, le=5)
    blocking: bool = False

    @field_validator("criterion_id", "question")
    @classmethod
    def normalized(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("human-review text must be normalized and nonblank")
        return value


class Stage9HumanReviewRubric(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    rubric_id: str
    version: str
    criteria: tuple[Stage9HumanReviewCriterion, ...] = Field(
        min_length=4, max_length=12
    )

    @model_validator(mode="after")
    def validate_rubric(self) -> Self:
        if not self.rubric_id.strip() or not self.version.strip():
            raise ValueError("rubric identity must not be blank")
        ids = [item.criterion_id.casefold() for item in self.criteria]
        dimensions = [item.dimension for item in self.criteria]
        if len(ids) != len(set(ids)) or len(dimensions) != len(set(dimensions)):
            raise ValueError("rubric criteria and dimensions must be unique")
        if set(dimensions) != set(HumanReviewDimension):
            raise ValueError("rubric must cover every required human-review dimension")
        return self


class Stage9EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    definition: EvaluationCaseDefinition
    domain: Stage9EvaluationDomain
    partition: Stage9DatasetPartition
    prohibited_claims: tuple[str, ...] = Field(min_length=1, max_length=32)
    expected_uncertainties: tuple[str, ...] = Field(min_length=1, max_length=32)
    human_review_required: bool = True

    @field_validator("prohibited_claims", "expected_uncertainties")
    @classmethod
    def normalized_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("case boundary text must be normalized and nonblank")
        if len(values) != len({value.casefold() for value in values}):
            raise ValueError("case boundary text must be unique")
        return values


class Stage9ExperimentManifest(BaseModel):
    """Frozen dataset, runtime, budget, ordering, and review conditions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    manifest_id: str
    manifest_version: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_profile_id: str
    architecture: str = Field(pattern=r"^bounded_single_agent$")
    provider_name: str
    model_name: str
    price_registry_version: str
    cases: tuple[Stage9EvaluationCase, ...] = Field(min_length=10, max_length=20)
    case_order: tuple[str, ...] = Field(min_length=10, max_length=20)
    repetitions_per_case: int = Field(default=1, ge=1, le=5)
    execution_budget: MonetaryCostBudget
    human_review_rubric: Stage9HumanReviewRubric

    @field_validator(
        "manifest_id",
        "manifest_version",
        "dataset_id",
        "dataset_version",
        "system_profile_id",
        "provider_name",
        "model_name",
        "price_registry_version",
    )
    @classmethod
    def normalized_identity(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("manifest identity fields must be normalized")
        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        ids = [item.definition.case_id for item in self.cases]
        if len(ids) != len({value.casefold() for value in ids}):
            raise ValueError("Stage 9 case IDs must be unique")
        if list(self.case_order) != ids:
            raise ValueError("case_order must exactly match the frozen case sequence")
        domains = {item.domain for item in self.cases}
        if domains != set(Stage9EvaluationDomain):
            raise ValueError("manifest must cover every required research domain")
        partitions = {item.partition for item in self.cases}
        if partitions != set(Stage9DatasetPartition):
            raise ValueError("manifest must contain development and locked cases")
        if not all(item.human_review_required for item in self.cases):
            raise ValueError("every real-research case requires human review")
        return self
