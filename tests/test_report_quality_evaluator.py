"""Tests for deterministic report quality evaluation."""

import pytest
from pydantic import ValidationError

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.report_quality_evaluator import (
    ReportQualityEvaluator,
)
from app.evals.report_quality_evaluator_error import (
    ReportQualityEvaluatorError,
)
from app.evals.report_quality_rubric import (
    ReportQualityCriterion,
    ReportQualityRubric,
    default_report_quality_rubric,
)
from app.evals.report_quality_snapshot import (
    ReportQualityObservation,
    ReportQualitySnapshot,
)


def observation(
    *,
    dimension: EvaluationDimension,
    score: float = 0.9,
) -> ReportQualityObservation:
    """Return one quality observation."""

    return ReportQualityObservation(
        dimension=dimension,
        score=score,
        rationale=(
            f"The report received {score:.2f} "
            f"for {dimension.value}."
        ),
        evaluator="test-quality-observer",
    )


def complete_snapshot(
    *,
    score: float = 0.9,
) -> ReportQualitySnapshot:
    """Return observations for all default criteria."""

    rubric = default_report_quality_rubric()

    return ReportQualitySnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        report_id="report-001",
        observations=[
            observation(
                dimension=criterion.dimension,
                score=score,
            )
            for criterion in rubric.criteria
        ],
    )


def evaluator(
    rubric: ReportQualityRubric | None = None,
) -> ReportQualityEvaluator:
    """Return one deterministic quality evaluator."""

    return ReportQualityEvaluator(
        rubric=rubric or default_report_quality_rubric(),
        evaluation_id_factory=(
            lambda: "report-quality-evaluation-001"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_default_rubric_has_expected_dimensions() -> None:
    rubric = default_report_quality_rubric()

    assert rubric.total_weight == pytest.approx(10.5)
    assert len(rubric.criteria) == 9
    assert rubric.criterion_for_dimension(
        EvaluationDimension.CLAIM_SUPPORT
    ) is not None
    assert len(rubric.required_criteria) == 8


def test_complete_high_quality_report_passes() -> None:
    value = evaluator().evaluate(
        complete_snapshot(score=0.9)
    )

    assert value.passed is True
    assert value.overall_score == pytest.approx(0.9)
    assert value.evaluated_criterion_count == 9
    assert value.missing_criterion_count == 0
    assert value.failed_required_criterion_count == 0
    assert value.failed_blocking_criterion_count == 0
    assert value.violations == []


def test_weighted_score_is_calculated() -> None:
    rubric = ReportQualityRubric(
        rubric_id="rubric-weighted",
        name="Weighted rubric",
        description="Test weighted score.",
        version="1.0.0",
        criteria=[
            ReportQualityCriterion(
                criterion_id="correctness",
                dimension=EvaluationDimension.CORRECTNESS,
                name="Correctness",
                description="Correctness criterion.",
                weight=3.0,
                minimum_score=0.5,
            ),
            ReportQualityCriterion(
                criterion_id="clarity",
                dimension=EvaluationDimension.CLARITY,
                name="Clarity",
                description="Clarity criterion.",
                weight=1.0,
                minimum_score=0.5,
            ),
        ],
        minimum_overall_score=0.5,
    )
    snapshot = ReportQualitySnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        report_id="report-001",
        observations=[
            observation(
                dimension=EvaluationDimension.CORRECTNESS,
                score=1.0,
            ),
            observation(
                dimension=EvaluationDimension.CLARITY,
                score=0.0,
            ),
        ],
    )

    value = evaluator(rubric).evaluate(snapshot)

    assert value.overall_score == pytest.approx(0.75)


def test_missing_required_dimension_fails() -> None:
    rubric = default_report_quality_rubric()
    snapshot = complete_snapshot()
    values = snapshot.model_dump(mode="python")
    values["observations"] = [
        item
        for item in values["observations"]
        if item["dimension"]
        != EvaluationDimension.CORRECTNESS
    ]
    snapshot = ReportQualitySnapshot.model_validate(values)

    value = evaluator(rubric).evaluate(snapshot)

    assert value.passed is False
    assert value.missing_criterion_count == 1
    assert value.failed_required_criterion_count == 1
    assert value.failed_blocking_criterion_count == 1
    assert any(
        violation.code
        == "MISSING_REPORT_QUALITY_DIMENSION"
        for violation in value.violations
    )


def test_blocking_score_failure_fails_report() -> None:
    snapshot = complete_snapshot()
    values = snapshot.model_dump(mode="python")

    for item in values["observations"]:
        if (
            item["dimension"]
            == EvaluationDimension.CLAIM_SUPPORT
        ):
            item["score"] = 0.4

    snapshot = ReportQualitySnapshot.model_validate(values)
    value = evaluator().evaluate(snapshot)

    assert value.passed is False
    assert value.failed_blocking_criterion_count == 1
    assert any(
        violation.code
        == "REPORT_QUALITY_SCORE_BELOW_THRESHOLD"
        for violation in value.violations
    )


def test_optional_missing_dimension_does_not_fail() -> None:
    snapshot = complete_snapshot()
    values = snapshot.model_dump(mode="python")
    values["observations"] = [
        item
        for item in values["observations"]
        if item["dimension"]
        != EvaluationDimension.LIMITATIONS_DISCLOSURE
    ]
    snapshot = ReportQualitySnapshot.model_validate(values)

    value = evaluator().evaluate(snapshot)

    assert value.passed is True
    assert value.missing_criterion_count == 1
    assert value.failed_required_criterion_count == 0


def test_required_failure_can_be_allowed_by_rubric() -> None:
    rubric = ReportQualityRubric(
        rubric_id="rubric-flexible",
        name="Flexible rubric",
        description="Allow required criterion failure.",
        version="1.0.0",
        criteria=[
            ReportQualityCriterion(
                criterion_id="clarity",
                dimension=EvaluationDimension.CLARITY,
                name="Clarity",
                description="Clarity criterion.",
                weight=1.0,
                minimum_score=0.8,
                required=True,
                blocking=False,
            ),
            ReportQualityCriterion(
                criterion_id="correctness",
                dimension=EvaluationDimension.CORRECTNESS,
                name="Correctness",
                description="Correctness criterion.",
                weight=3.0,
                minimum_score=0.8,
                required=True,
                blocking=False,
            ),
        ],
        minimum_overall_score=0.7,
        require_all_required_criteria=False,
    )
    snapshot = ReportQualitySnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        report_id="report-001",
        observations=[
            observation(
                dimension=EvaluationDimension.CLARITY,
                score=0.6,
            ),
            observation(
                dimension=EvaluationDimension.CORRECTNESS,
                score=1.0,
            ),
        ],
    )

    value = evaluator(rubric).evaluate(snapshot)

    assert value.overall_score == pytest.approx(0.9)
    assert value.failed_required_criterion_count == 1
    assert value.failed_blocking_criterion_count == 0
    assert value.passed is True


def test_rubric_rejects_duplicate_dimensions() -> None:
    with pytest.raises(
        ValidationError,
        match="criteria must have unique dimensions",
    ):
        ReportQualityRubric(
            rubric_id="rubric-invalid",
            name="Invalid rubric",
            description="Duplicate dimensions.",
            version="1.0.0",
            criteria=[
                ReportQualityCriterion(
                    criterion_id="clarity-1",
                    dimension=EvaluationDimension.CLARITY,
                    name="Clarity one",
                    description="First clarity criterion.",
                    weight=1.0,
                ),
                ReportQualityCriterion(
                    criterion_id="clarity-2",
                    dimension=EvaluationDimension.CLARITY,
                    name="Clarity two",
                    description="Second clarity criterion.",
                    weight=1.0,
                ),
            ],
        )


def test_blocking_criterion_must_be_required() -> None:
    with pytest.raises(
        ValidationError,
        match="blocking criterion must be required",
    ):
        ReportQualityCriterion(
            criterion_id="invalid",
            dimension=EvaluationDimension.CORRECTNESS,
            name="Invalid criterion",
            description="Blocking but optional.",
            weight=1.0,
            required=False,
            blocking=True,
        )


def test_snapshot_rejects_duplicate_dimensions() -> None:
    duplicate = observation(
        dimension=EvaluationDimension.CLARITY,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "observations must have unique dimensions"
        ),
    ):
        ReportQualitySnapshot(
            execution_id="execution-001",
            request_id="research-001",
            workspace_id="workspace-001",
            report_id="report-001",
            observations=[
                duplicate,
                duplicate,
            ],
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = ReportQualityEvaluator(
        rubric=default_report_quality_rubric(),
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        ReportQualityEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(complete_snapshot())
