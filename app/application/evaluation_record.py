"""Persistent application evaluation result schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


class ApplicationEvaluationStatus(StrEnum):
    """Persistent evaluation lifecycle outcome."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class ApplicationEvaluationType(StrEnum):
    """Normalized type of stored evaluation."""

    CITATION_CORRECTNESS = "citation_correctness"
    EVIDENCE_GROUNDING = "evidence_grounding"
    CLAIM_SUPPORT = "claim_support"
    REPORT_QUALITY = "report_quality"
    MULTI_AGENT_WORKFLOW = "multi_agent_workflow"
    REGRESSION = "regression"
    GUARDRAIL = "guardrail"
    RELIABILITY = "reliability"
    END_TO_END = "end_to_end"
    CUSTOM = "custom"


class ApplicationEvaluationDimensionScore(BaseModel):
    """Persistent score for one evaluation dimension."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dimension: str
    score: float = Field(ge=0, le=1)
    passed: bool
    summary: str

    @model_validator(mode="after")
    def validate_dimension(self) -> Self:
        """Validate one dimension score."""

        if not self.dimension.strip():
            raise ValueError(
                "dimension must not be blank"
            )

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        return self


class ApplicationEvaluationViolation(BaseModel):
    """Persistent normalized evaluation violation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    violation_id: str
    code: str
    message: str
    blocking: bool
    dimension: str | None = None
    reference_ids: list[str] = Field(default_factory=list)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_violation(self) -> Self:
        """Validate violation identity and references."""

        required_text = {
            "violation_id": self.violation_id,
            "code": self.code,
            "message": self.message,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.dimension is not None
            and not self.dimension.strip()
        ):
            raise ValueError(
                "dimension must not be blank when provided"
            )

        if any(
            not reference_id.strip()
            for reference_id in self.reference_ids
        ):
            raise ValueError(
                "reference_ids must not contain blank values"
            )

        normalized = [
            reference_id.strip().casefold()
            for reference_id in self.reference_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "reference_ids must not contain duplicates"
            )

        return self


class ApplicationEvaluationRecord(BaseModel):
    """Persistent application-level evaluation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    evaluation_type: ApplicationEvaluationType
    evaluator_name: str
    evaluator_version: str

    request_id: str
    workspace_id: str
    execution_id: str | None = None
    dataset_id: str | None = None
    case_id: str | None = None
    baseline_evaluation_id: str | None = None

    status: ApplicationEvaluationStatus
    overall_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    threshold_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    dimension_scores: list[
        ApplicationEvaluationDimensionScore
    ] = Field(default_factory=list)
    violations: list[
        ApplicationEvaluationViolation
    ] = Field(default_factory=list)

    result_payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    started_at: datetime
    finished_at: datetime

    record_version: int = Field(default=1, ge=1)
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate persistent evaluation invariants."""

        required_text = {
            "evaluation_id": self.evaluation_id,
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "execution_id": self.execution_id,
            "dataset_id": self.dataset_id,
            "case_id": self.case_id,
            "baseline_evaluation_id": (
                self.baseline_evaluation_id
            ),
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if self.started_at.tzinfo is None:
            raise ValueError(
                "started_at must be timezone-aware"
            )

        if self.finished_at.tzinfo is None:
            raise ValueError(
                "finished_at must be timezone-aware"
            )

        if self.finished_at < self.started_at:
            raise ValueError(
                "finished_at must not precede started_at"
            )

        if (
            self.status
            in {
                ApplicationEvaluationStatus.PASSED,
                ApplicationEvaluationStatus.FAILED,
            }
            and self.overall_score is None
        ):
            raise ValueError(
                "passed or failed evaluation requires "
                "overall_score"
            )

        if (
            self.status
            in {
                ApplicationEvaluationStatus.ERROR,
                ApplicationEvaluationStatus.SKIPPED,
            }
            and self.overall_score is not None
        ):
            raise ValueError(
                "error or skipped evaluation must not include "
                "overall_score"
            )

        if (
            self.threshold_score is not None
            and self.overall_score is None
        ):
            raise ValueError(
                "threshold_score requires overall_score"
            )

        if (
            self.status is ApplicationEvaluationStatus.PASSED
            and self.threshold_score is not None
            and self.overall_score is not None
            and self.overall_score < self.threshold_score
        ):
            raise ValueError(
                "passed evaluation score must meet threshold"
            )

        if (
            self.status is ApplicationEvaluationStatus.FAILED
            and self.threshold_score is not None
            and self.overall_score is not None
            and self.overall_score >= self.threshold_score
            and not self.blocking_violations
        ):
            raise ValueError(
                "failed evaluation requires score below "
                "threshold or blocking violation"
            )

        self._validate_dimension_scores()
        self._validate_violations()
        self._validate_metadata()

        return self

    def _validate_dimension_scores(self) -> None:
        """Validate dimension-score uniqueness."""

        normalized = [
            item.dimension.strip().casefold()
            for item in self.dimension_scores
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "dimension_scores must have unique dimensions"
            )

    def _validate_violations(self) -> None:
        """Validate violation identifier uniqueness."""

        normalized = [
            item.violation_id.strip().casefold()
            for item in self.violations
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "violations must have unique violation IDs"
            )

    def _validate_metadata(self) -> None:
        """Validate metadata values."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def blocking_violations(
        self,
    ) -> list[ApplicationEvaluationViolation]:
        """Return all blocking violations."""

        return [
            violation
            for violation in self.violations
            if violation.blocking
        ]

    @property
    def passed(self) -> bool:
        """Return whether evaluation passed."""

        return self.status is ApplicationEvaluationStatus.PASSED

    @property
    def duration_seconds(self) -> float:
        """Return evaluation duration in seconds."""

        return (
            self.finished_at - self.started_at
        ).total_seconds()
