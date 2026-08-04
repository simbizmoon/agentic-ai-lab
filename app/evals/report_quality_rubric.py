"""Schemas for deterministic report quality rubrics."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)


class ReportQualityCriterion(BaseModel):
    """One weighted report-quality criterion."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    criterion_id: str
    dimension: EvaluationDimension
    name: str
    description: str
    weight: float = Field(gt=0)
    minimum_score: float = Field(default=0.7, ge=0, le=1)
    required: bool = True
    blocking: bool = False
    guidance: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_criterion(self) -> Self:
        """Validate criterion text and configuration."""

        required_text = {
            "criterion_id": self.criterion_id,
            "name": self.name,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.blocking and not self.required:
            raise ValueError(
                "blocking criterion must be required"
            )

        self._validate_unique_text(
            self.guidance,
            field_name="guidance",
        )
        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique text values."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate string metadata."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class ReportQualityRubric(BaseModel):
    """Versioned weighted rubric for final research reports."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    rubric_id: str
    name: str
    description: str
    version: str
    criteria: list[ReportQualityCriterion] = Field(
        min_length=1
    )
    minimum_overall_score: float = Field(
        default=0.75,
        ge=0,
        le=1,
    )
    require_all_required_criteria: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rubric(self) -> Self:
        """Validate criterion uniqueness and rubric metadata."""

        required_text = {
            "rubric_id": self.rubric_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        criterion_ids = [
            criterion.criterion_id.strip().casefold()
            for criterion in self.criteria
        ]

        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError(
                "criteria must have unique criterion IDs"
            )

        dimensions = [
            criterion.dimension
            for criterion in self.criteria
        ]

        if len(set(dimensions)) != len(dimensions):
            raise ValueError(
                "criteria must have unique dimensions"
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

    @property
    def total_weight(self) -> float:
        """Return the total configured criterion weight."""

        return sum(
            criterion.weight
            for criterion in self.criteria
        )

    @property
    def required_criteria(
        self,
    ) -> list[ReportQualityCriterion]:
        """Return required rubric criteria."""

        return [
            criterion
            for criterion in self.criteria
            if criterion.required
        ]

    def criterion_for_dimension(
        self,
        dimension: EvaluationDimension,
    ) -> ReportQualityCriterion | None:
        """Return one criterion by evaluation dimension."""

        return next(
            (
                criterion
                for criterion in self.criteria
                if criterion.dimension is dimension
            ),
            None,
        )


def default_report_quality_rubric() -> ReportQualityRubric:
    """Return the default AIRA report-quality rubric."""

    return ReportQualityRubric(
        rubric_id="aira-report-quality-v1",
        name="AIRA Report Quality Rubric",
        description=(
            "Weighted baseline rubric for evaluating "
            "grounded research reports."
        ),
        version="1.0.0",
        criteria=[
            ReportQualityCriterion(
                criterion_id="relevance",
                dimension=EvaluationDimension.RELEVANCE,
                name="Relevance",
                description=(
                    "The report directly addresses "
                    "the research question."
                ),
                weight=1.0,
                minimum_score=0.7,
                required=True,
                blocking=True,
            ),
            ReportQualityCriterion(
                criterion_id="completeness",
                dimension=EvaluationDimension.COMPLETENESS,
                name="Completeness",
                description=(
                    "The report covers all required topics "
                    "and expected conclusions."
                ),
                weight=1.0,
                minimum_score=0.7,
                required=True,
            ),
            ReportQualityCriterion(
                criterion_id="correctness",
                dimension=EvaluationDimension.CORRECTNESS,
                name="Correctness",
                description=(
                    "The report avoids unsupported or "
                    "contradictory factual statements."
                ),
                weight=1.5,
                minimum_score=0.8,
                required=True,
                blocking=True,
            ),
            ReportQualityCriterion(
                criterion_id="evidence-grounding",
                dimension=(
                    EvaluationDimension.EVIDENCE_GROUNDING
                ),
                name="Evidence Grounding",
                description=(
                    "Important findings are grounded in "
                    "retrieved source evidence."
                ),
                weight=1.5,
                minimum_score=0.8,
                required=True,
                blocking=True,
            ),
            ReportQualityCriterion(
                criterion_id="claim-support",
                dimension=EvaluationDimension.CLAIM_SUPPORT,
                name="Claim Support",
                description=(
                    "Claims have sufficient and appropriate "
                    "supporting evidence."
                ),
                weight=1.5,
                minimum_score=0.8,
                required=True,
                blocking=True,
            ),
            ReportQualityCriterion(
                criterion_id="citation-correctness",
                dimension=(
                    EvaluationDimension.CITATION_CORRECTNESS
                ),
                name="Citation Correctness",
                description=(
                    "Citations correctly connect claims, "
                    "evidence, and sources."
                ),
                weight=1.5,
                minimum_score=0.8,
                required=True,
                blocking=True,
            ),
            ReportQualityCriterion(
                criterion_id="logical-consistency",
                dimension=(
                    EvaluationDimension.LOGICAL_CONSISTENCY
                ),
                name="Logical Consistency",
                description=(
                    "Sections and conclusions are logically "
                    "consistent with each other."
                ),
                weight=1.0,
                minimum_score=0.7,
                required=True,
            ),
            ReportQualityCriterion(
                criterion_id="clarity",
                dimension=EvaluationDimension.CLARITY,
                name="Clarity",
                description=(
                    "The report is understandable and "
                    "well organized."
                ),
                weight=0.75,
                minimum_score=0.7,
                required=True,
            ),
            ReportQualityCriterion(
                criterion_id="limitations",
                dimension=(
                    EvaluationDimension
                    .LIMITATIONS_DISCLOSURE
                ),
                name="Limitations Disclosure",
                description=(
                    "The report clearly identifies material "
                    "limitations and uncertainty."
                ),
                weight=0.75,
                minimum_score=0.6,
                required=False,
            ),
        ],
        minimum_overall_score=0.75,
        require_all_required_criteria=True,
    )
