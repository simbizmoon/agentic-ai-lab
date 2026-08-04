"""Compare baseline and current evaluation results for regressions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationCaseResult,
    EvaluationResultStatus,
)
from app.evals.regression_evaluation_runner_error import (
    RegressionEvaluationRunnerError,
)


class RegressionChangeType(StrEnum):
    """Type of change detected between evaluation results."""

    STATUS_REGRESSION = "status_regression"
    STATUS_IMPROVEMENT = "status_improvement"
    OVERALL_SCORE_REGRESSION = "overall_score_regression"
    OVERALL_SCORE_IMPROVEMENT = "overall_score_improvement"
    DIMENSION_REGRESSION = "dimension_regression"
    DIMENSION_IMPROVEMENT = "dimension_improvement"
    NEW_BLOCKING_VIOLATION = "new_blocking_violation"
    RESOLVED_BLOCKING_VIOLATION = (
        "resolved_blocking_violation"
    )
    TOKEN_USAGE_INCREASE = "token_usage_increase"
    TOKEN_USAGE_DECREASE = "token_usage_decrease"
    TOOL_CALL_INCREASE = "tool_call_increase"
    TOOL_CALL_DECREASE = "tool_call_decrease"


class RegressionSeverity(StrEnum):
    """Severity assigned to one detected regression change."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RegressionChange(BaseModel):
    """One detected change between baseline and current results."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    change_id: str
    change_type: RegressionChangeType
    severity: RegressionSeverity
    message: str
    regression: bool
    dimension: EvaluationDimension | None = None
    baseline_value: float | int | str | None = None
    current_value: float | int | str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class RegressionEvaluationResult(BaseModel):
    """Complete baseline-to-current regression comparison."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    comparison_id: str
    dataset_id: str
    dataset_version: str
    case_id: str
    baseline_result_id: str
    current_result_id: str
    regression_detected: bool
    changes: list[RegressionChange] = Field(
        default_factory=list
    )
    regression_count: int = Field(ge=0)
    improvement_count: int = Field(ge=0)
    baseline_overall_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    current_overall_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    summary: str

    @property
    def passed(self) -> bool:
        """Return whether no regression was detected."""

        return not self.regression_detected


class RegressionEvaluationRunner:
    """Compare one baseline and current evaluation result."""

    def __init__(
        self,
        *,
        overall_score_tolerance: float = 0.02,
        dimension_score_tolerance: float = 0.05,
        token_increase_tolerance: float = 0.25,
        tool_call_increase_tolerance: float = 0.25,
        comparison_id_factory: Callable[[], str] | None = None,
        change_id_factory: Callable[[int], str] | None = None,
    ) -> None:
        tolerance_values = {
            "overall_score_tolerance": overall_score_tolerance,
            "dimension_score_tolerance": (
                dimension_score_tolerance
            ),
            "token_increase_tolerance": token_increase_tolerance,
            "tool_call_increase_tolerance": (
                tool_call_increase_tolerance
            ),
        }

        for name, value in tolerance_values.items():
            if value < 0:
                raise ValueError(
                    f"{name} must be nonnegative"
                )

        self._overall_score_tolerance = (
            overall_score_tolerance
        )
        self._dimension_score_tolerance = (
            dimension_score_tolerance
        )
        self._token_increase_tolerance = (
            token_increase_tolerance
        )
        self._tool_call_increase_tolerance = (
            tool_call_increase_tolerance
        )
        self._comparison_id_factory = (
            comparison_id_factory
            or (lambda: f"regression-comparison-{uuid4()}")
        )
        self._change_id_factory = (
            change_id_factory
            or (
                lambda index: (
                    f"regression-change-{index}-{uuid4()}"
                )
            )
        )

    def compare(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
    ) -> RegressionEvaluationResult:
        """Compare baseline and current evaluation results."""

        self._validate_context(
            baseline=baseline,
            current=current,
        )

        changes: list[RegressionChange] = []

        self._compare_status(
            baseline=baseline,
            current=current,
            changes=changes,
        )
        self._compare_overall_score(
            baseline=baseline,
            current=current,
            changes=changes,
        )
        self._compare_dimensions(
            baseline=baseline,
            current=current,
            changes=changes,
        )
        self._compare_blocking_violations(
            baseline=baseline,
            current=current,
            changes=changes,
        )
        self._compare_efficiency(
            baseline=baseline,
            current=current,
            changes=changes,
        )

        regression_count = sum(
            change.regression
            for change in changes
        )
        improvement_count = sum(
            not change.regression
            and change.change_type
            in {
                RegressionChangeType.STATUS_IMPROVEMENT,
                RegressionChangeType
                .OVERALL_SCORE_IMPROVEMENT,
                RegressionChangeType.DIMENSION_IMPROVEMENT,
                RegressionChangeType
                .RESOLVED_BLOCKING_VIOLATION,
                RegressionChangeType.TOKEN_USAGE_DECREASE,
                RegressionChangeType.TOOL_CALL_DECREASE,
            }
            for change in changes
        )
        regression_detected = regression_count > 0

        return RegressionEvaluationResult(
            comparison_id=self._new_identifier(
                self._comparison_id_factory,
                field_name="comparison_id",
            ),
            dataset_id=baseline.dataset_id,
            dataset_version=baseline.dataset_version,
            case_id=baseline.case_id,
            baseline_result_id=baseline.result_id,
            current_result_id=current.result_id,
            regression_detected=regression_detected,
            changes=changes,
            regression_count=regression_count,
            improvement_count=improvement_count,
            baseline_overall_score=(
                baseline.overall_score
            ),
            current_overall_score=current.overall_score,
            summary=(
                "Regression comparison completed with "
                f"{regression_count} regressions and "
                f"{improvement_count} improvements."
            ),
        )

    def _compare_status(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
        changes: list[RegressionChange],
    ) -> None:
        """Compare evaluation result statuses."""

        baseline_passed = (
            baseline.status is EvaluationResultStatus.PASSED
        )
        current_passed = (
            current.status is EvaluationResultStatus.PASSED
        )

        if baseline_passed and not current_passed:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType.STATUS_REGRESSION
                    ),
                    severity=RegressionSeverity.CRITICAL,
                    message=(
                        "Evaluation status regressed from "
                        f"{baseline.status.value} to "
                        f"{current.status.value}."
                    ),
                    regression=True,
                    baseline_value=baseline.status.value,
                    current_value=current.status.value,
                )
            )
        elif not baseline_passed and current_passed:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType.STATUS_IMPROVEMENT
                    ),
                    severity=RegressionSeverity.INFO,
                    message=(
                        "Evaluation status improved from "
                        f"{baseline.status.value} to "
                        f"{current.status.value}."
                    ),
                    regression=False,
                    baseline_value=baseline.status.value,
                    current_value=current.status.value,
                )
            )

    def _compare_overall_score(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
        changes: list[RegressionChange],
    ) -> None:
        """Compare overall evaluation scores."""

        if (
            baseline.overall_score is None
            or current.overall_score is None
        ):
            return

        difference = (
            current.overall_score
            - baseline.overall_score
        )

        if difference < -self._overall_score_tolerance:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType
                        .OVERALL_SCORE_REGRESSION
                    ),
                    severity=RegressionSeverity.ERROR,
                    message=(
                        "Overall evaluation score decreased "
                        "beyond the configured tolerance."
                    ),
                    regression=True,
                    baseline_value=baseline.overall_score,
                    current_value=current.overall_score,
                )
            )
        elif difference > self._overall_score_tolerance:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType
                        .OVERALL_SCORE_IMPROVEMENT
                    ),
                    severity=RegressionSeverity.INFO,
                    message=(
                        "Overall evaluation score improved "
                        "beyond the configured tolerance."
                    ),
                    regression=False,
                    baseline_value=baseline.overall_score,
                    current_value=current.overall_score,
                )
            )

    def _compare_dimensions(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
        changes: list[RegressionChange],
    ) -> None:
        """Compare matching evaluation dimension scores."""

        baseline_scores = {
            score.dimension: score.score
            for score in baseline.dimension_scores
        }
        current_scores = {
            score.dimension: score.score
            for score in current.dimension_scores
        }

        for dimension in sorted(
            set(baseline_scores) & set(current_scores),
            key=lambda item: item.value,
        ):
            baseline_score = baseline_scores[dimension]
            current_score = current_scores[dimension]
            difference = current_score - baseline_score

            if difference < -self._dimension_score_tolerance:
                changes.append(
                    self._change(
                        index=len(changes) + 1,
                        change_type=(
                            RegressionChangeType
                            .DIMENSION_REGRESSION
                        ),
                        severity=RegressionSeverity.ERROR,
                        message=(
                            "Evaluation dimension score "
                            f"decreased: {dimension.value}."
                        ),
                        regression=True,
                        dimension=dimension,
                        baseline_value=baseline_score,
                        current_value=current_score,
                    )
                )
            elif (
                difference
                > self._dimension_score_tolerance
            ):
                changes.append(
                    self._change(
                        index=len(changes) + 1,
                        change_type=(
                            RegressionChangeType
                            .DIMENSION_IMPROVEMENT
                        ),
                        severity=RegressionSeverity.INFO,
                        message=(
                            "Evaluation dimension score "
                            f"improved: {dimension.value}."
                        ),
                        regression=False,
                        dimension=dimension,
                        baseline_value=baseline_score,
                        current_value=current_score,
                    )
                )

    def _compare_blocking_violations(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
        changes: list[RegressionChange],
    ) -> None:
        """Compare blocking violation codes."""

        baseline_codes = {
            violation.code
            for violation in baseline.blocking_violations
        }
        current_codes = {
            violation.code
            for violation in current.blocking_violations
        }

        new_codes = current_codes - baseline_codes
        resolved_codes = baseline_codes - current_codes

        for code in sorted(new_codes):
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType
                        .NEW_BLOCKING_VIOLATION
                    ),
                    severity=RegressionSeverity.CRITICAL,
                    message=(
                        "A new blocking violation appeared: "
                        f"{code}."
                    ),
                    regression=True,
                    baseline_value="absent",
                    current_value=code,
                )
            )

        for code in sorted(resolved_codes):
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=(
                        RegressionChangeType
                        .RESOLVED_BLOCKING_VIOLATION
                    ),
                    severity=RegressionSeverity.INFO,
                    message=(
                        "A blocking violation was resolved: "
                        f"{code}."
                    ),
                    regression=False,
                    baseline_value=code,
                    current_value="absent",
                )
            )

    def _compare_efficiency(
        self,
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
        changes: list[RegressionChange],
    ) -> None:
        """Compare token and tool-call usage."""

        self._compare_count_metric(
            baseline_value=(
                baseline.metrics.total_token_count
            ),
            current_value=(
                current.metrics.total_token_count
            ),
            increase_tolerance=(
                self._token_increase_tolerance
            ),
            increase_type=(
                RegressionChangeType.TOKEN_USAGE_INCREASE
            ),
            decrease_type=(
                RegressionChangeType.TOKEN_USAGE_DECREASE
            ),
            label="Token usage",
            changes=changes,
        )
        self._compare_count_metric(
            baseline_value=baseline.metrics.tool_call_count,
            current_value=current.metrics.tool_call_count,
            increase_tolerance=(
                self._tool_call_increase_tolerance
            ),
            increase_type=(
                RegressionChangeType.TOOL_CALL_INCREASE
            ),
            decrease_type=(
                RegressionChangeType.TOOL_CALL_DECREASE
            ),
            label="Tool-call count",
            changes=changes,
        )

    def _compare_count_metric(
        self,
        *,
        baseline_value: int,
        current_value: int,
        increase_tolerance: float,
        increase_type: RegressionChangeType,
        decrease_type: RegressionChangeType,
        label: str,
        changes: list[RegressionChange],
    ) -> None:
        """Compare one nonnegative count metric."""

        if baseline_value == 0:
            if current_value > 0:
                changes.append(
                    self._change(
                        index=len(changes) + 1,
                        change_type=increase_type,
                        severity=RegressionSeverity.WARNING,
                        message=f"{label} increased from zero.",
                        regression=False,
                        baseline_value=baseline_value,
                        current_value=current_value,
                    )
                )

            return

        ratio = (
            current_value - baseline_value
        ) / baseline_value

        if ratio > increase_tolerance:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=increase_type,
                    severity=RegressionSeverity.WARNING,
                    message=(
                        f"{label} increased beyond "
                        "the configured tolerance."
                    ),
                    regression=False,
                    baseline_value=baseline_value,
                    current_value=current_value,
                )
            )
        elif ratio < -increase_tolerance:
            changes.append(
                self._change(
                    index=len(changes) + 1,
                    change_type=decrease_type,
                    severity=RegressionSeverity.INFO,
                    message=(
                        f"{label} decreased beyond "
                        "the configured tolerance."
                    ),
                    regression=False,
                    baseline_value=baseline_value,
                    current_value=current_value,
                )
            )

    def _change(
        self,
        *,
        index: int,
        change_type: RegressionChangeType,
        severity: RegressionSeverity,
        message: str,
        regression: bool,
        baseline_value: float | str | None,
        current_value: float | str | None,
        dimension: EvaluationDimension | None = None,
    ) -> RegressionChange:
        """Build one normalized regression change."""

        return RegressionChange(
            change_id=self._new_indexed_identifier(
                self._change_id_factory,
                index=index,
                field_name="change_id",
            ),
            change_type=change_type,
            severity=severity,
            message=message,
            regression=regression,
            dimension=dimension,
            baseline_value=baseline_value,
            current_value=current_value,
        )

    @staticmethod
    def _validate_context(
        *,
        baseline: EvaluationCaseResult,
        current: EvaluationCaseResult,
    ) -> None:
        """Require results to describe the same evaluation case."""

        fields = (
            "dataset_id",
            "dataset_version",
            "case_id",
            "request_id",
            "workspace_id",
        )

        for field_name in fields:
            if (
                getattr(baseline, field_name)
                != getattr(current, field_name)
            ):
                raise RegressionEvaluationRunnerError(
                    "baseline and current results must share "
                    f"{field_name}"
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
            raise RegressionEvaluationRunnerError(
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
            raise RegressionEvaluationRunnerError(
                f"{field_name} factory returned blank value"
            )

        return value
