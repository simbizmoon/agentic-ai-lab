"""Deterministic weighted report quality evaluation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.evals.evaluation_result import (
    EvaluationDimensionScore,
    EvaluationViolation,
    EvaluationViolationSeverity,
)
from app.evals.report_quality_evaluator_error import (
    ReportQualityEvaluatorError,
)
from app.evals.report_quality_rubric import (
    ReportQualityCriterion,
    ReportQualityRubric,
)
from app.evals.report_quality_snapshot import (
    ReportQualityObservation,
    ReportQualitySnapshot,
)


class ReportQualityCriterionResult(BaseModel):
    """Evaluated result for one report-quality criterion."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    criterion_id: str
    weight: float = Field(gt=0)
    weighted_score: float = Field(ge=0)
    score: EvaluationDimensionScore
    blocking: bool


class ReportQualityEvaluation(BaseModel):
    """Complete weighted report-quality evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    execution_id: str
    report_id: str
    rubric_id: str
    rubric_version: str
    overall_score: float = Field(ge=0, le=1)
    passed: bool
    criterion_results: list[
        ReportQualityCriterionResult
    ] = Field(default_factory=list)
    violations: list[EvaluationViolation] = Field(
        default_factory=list
    )
    evaluated_criterion_count: int = Field(ge=0)
    missing_criterion_count: int = Field(ge=0)
    failed_required_criterion_count: int = Field(ge=0)
    failed_blocking_criterion_count: int = Field(ge=0)


class ReportQualityEvaluator:
    """Evaluate report observations against a weighted rubric."""

    def __init__(
        self,
        *,
        rubric: ReportQualityRubric,
        evaluation_id_factory: Callable[[], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
        evaluator_name: str = (
            "deterministic-report-quality-evaluator"
        ),
    ) -> None:
        if not evaluator_name.strip():
            raise ValueError(
                "evaluator_name must not be blank"
            )

        self._rubric = rubric
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"report-quality-{uuid4()}")
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"report-quality-violation-{index}-{uuid4()}"
                )
            )
        )
        self._evaluator_name = evaluator_name

    def evaluate(
        self,
        snapshot: ReportQualitySnapshot,
    ) -> ReportQualityEvaluation:
        """Evaluate one report-quality snapshot."""

        observations = {
            observation.dimension: observation
            for observation in snapshot.observations
        }
        criterion_results: list[
            ReportQualityCriterionResult
        ] = []
        violations: list[EvaluationViolation] = []

        weighted_score_sum = 0.0
        evaluated_weight_sum = 0.0
        missing_count = 0
        failed_required_count = 0
        failed_blocking_count = 0

        for criterion in self._rubric.criteria:
            observation = observations.get(
                criterion.dimension
            )

            if observation is None:
                missing_count += 1

                if criterion.required:
                    failed_required_count += 1

                    if criterion.blocking:
                        failed_blocking_count += 1

                    violations.append(
                        self._missing_violation(
                            index=len(violations) + 1,
                            criterion=criterion,
                        )
                    )

                continue

            passed = (
                observation.score
                >= criterion.minimum_score
            )
            dimension_score = EvaluationDimensionScore(
                dimension=criterion.dimension,
                score=observation.score,
                threshold=criterion.minimum_score,
                required=criterion.required,
                passed=passed,
                rationale=observation.rationale,
                evaluator=observation.evaluator,
                metadata={
                    **observation.metadata,
                    "criterion_id": criterion.criterion_id,
                },
            )
            weighted_score = (
                observation.score * criterion.weight
            )

            criterion_results.append(
                ReportQualityCriterionResult(
                    criterion_id=criterion.criterion_id,
                    weight=criterion.weight,
                    weighted_score=weighted_score,
                    score=dimension_score,
                    blocking=criterion.blocking,
                )
            )
            weighted_score_sum += weighted_score
            evaluated_weight_sum += criterion.weight

            if not passed and criterion.required:
                failed_required_count += 1

                if criterion.blocking:
                    failed_blocking_count += 1

                violations.append(
                    self._failed_violation(
                        index=len(violations) + 1,
                        criterion=criterion,
                        observation=observation,
                    )
                )

        overall_score = (
            weighted_score_sum / evaluated_weight_sum
            if evaluated_weight_sum
            else 0.0
        )
        required_failure = (
            self._rubric.require_all_required_criteria
            and failed_required_count > 0
        )
        passed = (
            overall_score
            >= self._rubric.minimum_overall_score
            and failed_blocking_count == 0
            and not required_failure
        )

        return ReportQualityEvaluation(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            execution_id=snapshot.execution_id,
            report_id=snapshot.report_id,
            rubric_id=self._rubric.rubric_id,
            rubric_version=self._rubric.version,
            overall_score=overall_score,
            passed=passed,
            criterion_results=criterion_results,
            violations=violations,
            evaluated_criterion_count=len(
                criterion_results
            ),
            missing_criterion_count=missing_count,
            failed_required_criterion_count=(
                failed_required_count
            ),
            failed_blocking_criterion_count=(
                failed_blocking_count
            ),
        )

    def _missing_violation(
        self,
        *,
        index: int,
        criterion: ReportQualityCriterion,
    ) -> EvaluationViolation:
        """Build one missing criterion violation."""

        return EvaluationViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            code="MISSING_REPORT_QUALITY_DIMENSION",
            severity=(
                EvaluationViolationSeverity.CRITICAL
                if criterion.blocking
                else EvaluationViolationSeverity.ERROR
            ),
            message=(
                "Required report quality dimension "
                f"was not evaluated: "
                f"{criterion.dimension.value}"
            ),
            blocking=criterion.blocking,
            dimension=criterion.dimension,
            remediation=(
                "Provide a quality observation for "
                "the required dimension."
            ),
            details={
                "criterion_id": criterion.criterion_id,
                "minimum_score": criterion.minimum_score,
            },
        )

    def _failed_violation(
        self,
        *,
        index: int,
        criterion: ReportQualityCriterion,
        observation: ReportQualityObservation,
    ) -> EvaluationViolation:
        """Build one failed criterion violation."""

        return EvaluationViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            code="REPORT_QUALITY_SCORE_BELOW_THRESHOLD",
            severity=(
                EvaluationViolationSeverity.CRITICAL
                if criterion.blocking
                else EvaluationViolationSeverity.ERROR
            ),
            message=(
                "Report quality score is below threshold "
                f"for {criterion.dimension.value}."
            ),
            blocking=criterion.blocking,
            dimension=criterion.dimension,
            remediation=(
                "Revise the report to satisfy "
                "the quality criterion."
            ),
            details={
                "criterion_id": criterion.criterion_id,
                "actual_score": observation.score,
                "minimum_score": criterion.minimum_score,
            },
        )

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate one nonblank identifier."""

        value = factory()

        if not value.strip():
            raise ReportQualityEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value

    @staticmethod
    def _new_indexed_identifier(
        factory: Callable[[int], str],
        *,
        index: int,
        field_name: str,
    ) -> str:
        """Generate one nonblank indexed identifier."""

        value = factory(index)

        if not value.strip():
            raise ReportQualityEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
