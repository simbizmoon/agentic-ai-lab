"""Schemas for deterministic research evaluation results."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)


class EvaluationResultStatus(StrEnum):
    """Terminal status of one evaluation execution."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"
    SKIPPED = "skipped"


class EvaluationViolationSeverity(StrEnum):
    """Severity assigned to one evaluation violation."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EvaluationFindingStatus(StrEnum):
    """Match status for one expected evaluation artifact."""

    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    MISSING = "missing"
    UNEXPECTED = "unexpected"
    NOT_EVALUATED = "not_evaluated"


class EvaluationArtifactType(StrEnum):
    """Artifact type evaluated in a research result."""

    SOURCE = "source"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    CITATION = "citation"
    REPORT_ELEMENT = "report_element"
    WORKFLOW = "workflow"


class EvaluationDimensionScore(BaseModel):
    """Score and rationale for one evaluation dimension."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    dimension: EvaluationDimension
    score: float = Field(ge=0, le=1)
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    required: bool = True
    passed: bool
    rationale: str
    evaluator: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dimension_score(self) -> Self:
        """Validate threshold consistency and text fields."""

        if not self.rationale.strip():
            raise ValueError(
                "rationale must not be blank"
            )

        if not self.evaluator.strip():
            raise ValueError(
                "evaluator must not be blank"
            )

        if self.threshold is not None:
            expected_passed = self.score >= self.threshold

            if self.passed != expected_passed:
                raise ValueError(
                    "passed must match score threshold result"
                )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class EvaluationArtifactFinding(BaseModel):
    """Evaluation finding for one expected or unexpected artifact."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    finding_id: str
    artifact_type: EvaluationArtifactType
    expected_artifact_id: str | None = None
    actual_artifact_id: str | None = None
    status: EvaluationFindingStatus
    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_finding(self) -> Self:
        """Validate artifact finding identity and semantics."""

        if not self.finding_id.strip():
            raise ValueError(
                "finding_id must not be blank"
            )

        if (
            self.expected_artifact_id is not None
            and not self.expected_artifact_id.strip()
        ):
            raise ValueError(
                "expected_artifact_id must not be blank "
                "when provided"
            )

        if (
            self.actual_artifact_id is not None
            and not self.actual_artifact_id.strip()
        ):
            raise ValueError(
                "actual_artifact_id must not be blank "
                "when provided"
            )

        if not self.explanation.strip():
            raise ValueError(
                "explanation must not be blank"
            )

        if (
            self.status
            in {
                EvaluationFindingStatus.MATCHED,
                EvaluationFindingStatus.PARTIAL_MATCH,
            }
            and self.actual_artifact_id is None
        ):
            raise ValueError(
                "matched finding must include "
                "actual_artifact_id"
            )

        if (
            self.status is EvaluationFindingStatus.MISSING
            and self.expected_artifact_id is None
        ):
            raise ValueError(
                "missing finding must include "
                "expected_artifact_id"
            )

        if (
            self.status is EvaluationFindingStatus.UNEXPECTED
            and self.actual_artifact_id is None
        ):
            raise ValueError(
                "unexpected finding must include "
                "actual_artifact_id"
            )

        self._validate_unique_text(
            self.evidence,
            field_name="evidence",
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
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class EvaluationViolation(BaseModel):
    """One policy, quality, or workflow violation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    violation_id: str
    code: str
    severity: EvaluationViolationSeverity
    message: str
    blocking: bool = False
    dimension: EvaluationDimension | None = None
    artifact_type: EvaluationArtifactType | None = None
    artifact_id: str | None = None
    remediation: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_violation(self) -> Self:
        """Validate violation fields."""

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
            self.artifact_id is not None
            and not self.artifact_id.strip()
        ):
            raise ValueError(
                "artifact_id must not be blank when provided"
            )

        if (
            self.remediation is not None
            and not self.remediation.strip()
        ):
            raise ValueError(
                "remediation must not be blank when provided"
            )

        return self


class EvaluationExecutionMetrics(BaseModel):
    """Execution and evaluation metrics for one case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    duration_ms: int = Field(default=0, ge=0)
    evaluator_call_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    source_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    claim_count: int = Field(default=0, ge=0)
    citation_count: int = Field(default=0, ge=0)
    revision_round_count: int = Field(default=0, ge=0)

    @property
    def total_token_count(self) -> int:
        """Return total token usage."""

        return (
            self.input_token_count
            + self.output_token_count
        )


class EvaluationError(BaseModel):
    """Structured error raised during evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    code: str
    message: str
    retryable: bool = False
    stage: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        """Validate error fields."""

        if not self.code.strip():
            raise ValueError(
                "code must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        if self.stage is not None and not self.stage.strip():
            raise ValueError(
                "stage must not be blank when provided"
            )

        return self


class EvaluationCaseResult(BaseModel):
    """Complete result for one evaluation case execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    result_id: str
    run_id: str
    dataset_id: str
    dataset_version: str
    case_id: str
    request_id: str
    workspace_id: str
    execution_id: str
    status: EvaluationResultStatus
    overall_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    dimension_scores: list[
        EvaluationDimensionScore
    ] = Field(default_factory=list)
    findings: list[
        EvaluationArtifactFinding
    ] = Field(default_factory=list)
    violations: list[
        EvaluationViolation
    ] = Field(default_factory=list)
    metrics: EvaluationExecutionMetrics = Field(
        default_factory=EvaluationExecutionMetrics
    )
    summary: str
    error: EvaluationError | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate evaluation status and result consistency."""

        required_text = {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "case_id": self.case_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "execution_id": self.execution_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_ids(
            [
                score.dimension.value
                for score in self.dimension_scores
            ],
            field_name="dimension score dimensions",
        )
        self._validate_unique_ids(
            [
                finding.finding_id
                for finding in self.findings
            ],
            field_name="finding IDs",
        )
        self._validate_unique_ids(
            [
                violation.violation_id
                for violation in self.violations
            ],
            field_name="violation IDs",
        )

        blocking_violations = [
            violation
            for violation in self.violations
            if violation.blocking
        ]

        if (
            self.status is EvaluationResultStatus.PASSED
            and blocking_violations
        ):
            raise ValueError(
                "passed result must not contain "
                "blocking violations"
            )

        if self.status in {
            EvaluationResultStatus.PASSED,
            EvaluationResultStatus.FAILED,
            EvaluationResultStatus.PARTIAL,
        }:
            if self.overall_score is None:
                raise ValueError(
                    "scored result must include overall_score"
                )

            if self.error is not None:
                raise ValueError(
                    "scored result must not include error"
                )

        if self.status is EvaluationResultStatus.ERROR:
            if self.error is None:
                raise ValueError(
                    "error result must include error"
                )

            if self.overall_score is not None:
                raise ValueError(
                    "error result must not include overall_score"
                )

        if self.status is EvaluationResultStatus.SKIPPED:
            if self.error is not None:
                raise ValueError(
                    "skipped result must not include error"
                )

            if self.overall_score is not None:
                raise ValueError(
                    "skipped result must not include "
                    "overall_score"
                )

        required_failed_scores = [
            score
            for score in self.dimension_scores
            if score.required and not score.passed
        ]

        if (
            self.status is EvaluationResultStatus.PASSED
            and required_failed_scores
        ):
            raise ValueError(
                "passed result must not contain failed "
                "required dimension scores"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_ids(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique identifiers."""

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
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def passed(self) -> bool:
        """Return whether the evaluation passed."""

        return self.status is EvaluationResultStatus.PASSED

    @property
    def blocking_violations(
        self,
    ) -> list[EvaluationViolation]:
        """Return blocking violations."""

        return [
            violation
            for violation in self.violations
            if violation.blocking
        ]

    @property
    def failed_required_dimensions(
        self,
    ) -> list[EvaluationDimensionScore]:
        """Return failed required dimension scores."""

        return [
            score
            for score in self.dimension_scores
            if score.required and not score.passed
        ]
