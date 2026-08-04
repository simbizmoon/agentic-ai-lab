"""Normalized observations supplied to report quality evaluation."""

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


class ReportQualityObservation(BaseModel):
    """One observed report-quality dimension score."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dimension: EvaluationDimension
    score: float = Field(ge=0, le=1)
    rationale: str
    evaluator: str
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        """Validate observation text and evidence."""

        if not self.rationale.strip():
            raise ValueError(
                "rationale must not be blank"
            )

        if not self.evaluator.strip():
            raise ValueError(
                "evaluator must not be blank"
            )

        self._validate_unique_text(
            self.evidence,
            field_name="evidence",
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
        """Validate unique nonblank text values."""

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


class ReportQualitySnapshot(BaseModel):
    """Observed report-quality scores for one execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    request_id: str
    workspace_id: str
    report_id: str
    observations: list[ReportQualityObservation] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate snapshot identity and unique dimensions."""

        required_text = {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "report_id": self.report_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        dimensions = [
            observation.dimension
            for observation in self.observations
        ]

        if len(set(dimensions)) != len(dimensions):
            raise ValueError(
                "observations must have unique dimensions"
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
