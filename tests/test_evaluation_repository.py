"""Tests for evaluation records and repositories."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.evaluation_record import (
    ApplicationEvaluationDimensionScore,
    ApplicationEvaluationRecord,
    ApplicationEvaluationStatus,
    ApplicationEvaluationType,
    ApplicationEvaluationViolation,
)
from app.application.evaluation_repository_error import (
    ApplicationEvaluationAlreadyExistsError,
    ApplicationEvaluationNotFoundError,
    ApplicationEvaluationVersionConflictError,
)
from app.application.evaluation_repository_query import (
    ApplicationEvaluationQuery,
    ApplicationEvaluationSortDirection,
    ApplicationEvaluationSortField,
)
from app.application.in_memory_evaluation_repository import (
    InMemoryApplicationEvaluationRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    40,
    tzinfo=UTC,
)


def violation(
    *,
    violation_id: str = "violation-001",
    blocking: bool = True,
) -> ApplicationEvaluationViolation:
    """Return one evaluation violation."""

    return ApplicationEvaluationViolation(
        violation_id=violation_id,
        code="MISSING_SUPPORT",
        message="Required evidence was not found.",
        blocking=blocking,
        dimension="grounding",
        reference_ids=["claim-001"],
    )


def record(
    *,
    evaluation_id: str,
    status: ApplicationEvaluationStatus = (
        ApplicationEvaluationStatus.PASSED
    ),
    overall_score: float | None = 0.9,
    threshold_score: float | None = 0.7,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    execution_id: str | None = "execution-001",
    evaluation_type: ApplicationEvaluationType = (
        ApplicationEvaluationType.CLAIM_SUPPORT
    ),
    started_offset: int = 0,
    violations: list[
        ApplicationEvaluationViolation
    ] | None = None,
    record_version: int = 1,
) -> ApplicationEvaluationRecord:
    """Return one persistent evaluation record."""

    return ApplicationEvaluationRecord(
        evaluation_id=evaluation_id,
        evaluation_type=evaluation_type,
        evaluator_name="claim-support-evaluator",
        evaluator_version="1.0.0",
        request_id=request_id,
        workspace_id=workspace_id,
        execution_id=execution_id,
        dataset_id="dataset-001",
        case_id="case-001",
        status=status,
        overall_score=overall_score,
        threshold_score=threshold_score,
        dimension_scores=[
            ApplicationEvaluationDimensionScore(
                dimension="grounding",
                score=overall_score or 0.0,
                passed=(
                    status
                    is ApplicationEvaluationStatus.PASSED
                ),
                summary="Grounding dimension result.",
            )
        ],
        violations=violations or [],
        result_payload={
            "case_id": "case-001",
            "status": status.value,
        },
        started_at=(
            BASE_TIME + timedelta(seconds=started_offset)
        ),
        finished_at=(
            BASE_TIME
            + timedelta(seconds=started_offset + 2)
        ),
        record_version=record_version,
        summary="Evaluation completed.",
    )


def repository_with_records(
) -> InMemoryApplicationEvaluationRepository:
    """Return a populated evaluation repository."""

    return InMemoryApplicationEvaluationRepository(
        [
            record(
                evaluation_id="evaluation-001",
                overall_score=0.95,
                started_offset=1,
            ),
            record(
                evaluation_id="evaluation-002",
                status=ApplicationEvaluationStatus.FAILED,
                overall_score=0.5,
                started_offset=2,
                violations=[violation()],
            ),
            record(
                evaluation_id="evaluation-003",
                request_id="research-002",
                workspace_id="workspace-002",
                execution_id="execution-002",
                evaluation_type=(
                    ApplicationEvaluationType.REPORT_QUALITY
                ),
                overall_score=0.8,
                started_offset=3,
            ),
        ]
    )


def test_evaluation_record_properties() -> None:
    value = record(evaluation_id="evaluation-001")

    assert value.passed is True
    assert value.duration_seconds == pytest.approx(2.0)
    assert value.blocking_violations == []


def test_failed_record_exposes_blocking_violations() -> None:
    value = record(
        evaluation_id="evaluation-001",
        status=ApplicationEvaluationStatus.FAILED,
        overall_score=0.5,
        violations=[violation()],
    )

    assert value.passed is False
    assert len(value.blocking_violations) == 1


def test_passed_evaluation_requires_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "passed or failed evaluation requires "
            "overall_score"
        ),
    ):
        record(
            evaluation_id="evaluation-invalid",
            overall_score=None,
            threshold_score=None,
        )


def test_error_evaluation_rejects_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "error or skipped evaluation must not include "
            "overall_score"
        ),
    ):
        record(
            evaluation_id="evaluation-invalid",
            status=ApplicationEvaluationStatus.ERROR,
            overall_score=0.2,
            threshold_score=None,
        )


def test_passed_score_must_meet_threshold() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "passed evaluation score must meet threshold"
        ),
    ):
        record(
            evaluation_id="evaluation-invalid",
            overall_score=0.5,
            threshold_score=0.7,
        )


def test_failed_result_needs_score_failure_or_block() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed evaluation requires score below "
            "threshold or blocking violation"
        ),
    ):
        record(
            evaluation_id="evaluation-invalid",
            status=ApplicationEvaluationStatus.FAILED,
            overall_score=0.9,
            threshold_score=0.7,
        )


def test_create_and_case_insensitive_get() -> None:
    repository = InMemoryApplicationEvaluationRepository()
    stored = record(evaluation_id="Evaluation-001")

    repository.create(stored)

    assert repository.get("evaluation-001") == stored
    assert repository.exists("EVALUATION-001") is True


def test_duplicate_evaluation_is_rejected() -> None:
    repository = InMemoryApplicationEvaluationRepository(
        [record(evaluation_id="Evaluation-001")]
    )

    with pytest.raises(
        ApplicationEvaluationAlreadyExistsError,
        match=(
            "application evaluation already exists: "
            "evaluation-001"
        ),
    ):
        repository.create(
            record(evaluation_id="evaluation-001")
        )


def test_require_missing_evaluation_fails() -> None:
    repository = InMemoryApplicationEvaluationRepository()

    with pytest.raises(
        ApplicationEvaluationNotFoundError,
        match=(
            "application evaluation was not found: "
            "evaluation-missing"
        ),
    ):
        repository.require("evaluation-missing")


def test_update_uses_optimistic_concurrency() -> None:
    repository = InMemoryApplicationEvaluationRepository()
    original = record(evaluation_id="evaluation-001")
    repository.create(original)

    updated = original.model_copy(
        update={
            "summary": "Updated evaluation.",
            "record_version": 2,
        }
    )

    result = repository.update(
        updated,
        expected_version=1,
    )

    assert result.record_version == 2
    assert repository.require(
        "evaluation-001"
    ).summary == "Updated evaluation."


def test_update_rejects_stale_version() -> None:
    original = record(
        evaluation_id="evaluation-001",
        record_version=2,
    )
    repository = InMemoryApplicationEvaluationRepository(
        [original]
    )

    updated = original.model_copy(
        update={"record_version": 3}
    )

    with pytest.raises(
        ApplicationEvaluationVersionConflictError,
        match=(
            "application evaluation version conflict: "
            "expected 1, stored 2"
        ),
    ):
        repository.update(
            updated,
            expected_version=1,
        )


def test_default_list_is_finished_descending() -> None:
    page = repository_with_records().list(
        ApplicationEvaluationQuery()
    )

    assert [
        item.evaluation_id
        for item in page.items
    ] == [
        "evaluation-003",
        "evaluation-002",
        "evaluation-001",
    ]


def test_filter_by_status_and_type() -> None:
    page = repository_with_records().list(
        ApplicationEvaluationQuery(
            statuses=[
                ApplicationEvaluationStatus.PASSED,
            ],
            evaluation_types=[
                ApplicationEvaluationType
                .REPORT_QUALITY,
            ],
        )
    )

    assert len(page.items) == 1
    assert page.items[0].evaluation_id == "evaluation-003"


def test_filter_by_request_workspace_and_execution() -> None:
    page = repository_with_records().list(
        ApplicationEvaluationQuery(
            request_id="research-002",
            workspace_id="workspace-002",
            execution_id="execution-002",
        )
    )

    assert len(page.items) == 1
    assert page.items[0].evaluation_id == "evaluation-003"


def test_filter_by_score_range() -> None:
    page = repository_with_records().list(
        ApplicationEvaluationQuery(
            minimum_score=0.8,
            maximum_score=0.95,
        )
    )

    assert {
        item.evaluation_id
        for item in page.items
    } == {
        "evaluation-001",
        "evaluation-003",
    }


def test_filter_blocking_results() -> None:
    repository = repository_with_records()

    blocking = repository.list(
        ApplicationEvaluationQuery(
            blocking_only=True
        )
    )
    nonblocking = repository.list(
        ApplicationEvaluationQuery(
            blocking_only=False
        )
    )

    assert [
        item.evaluation_id
        for item in blocking.items
    ] == ["evaluation-002"]

    assert {
        item.evaluation_id
        for item in nonblocking.items
    } == {
        "evaluation-001",
        "evaluation-003",
    }


def test_sort_score_ascending() -> None:
    page = repository_with_records().list(
        ApplicationEvaluationQuery(
            sort_field=(
                ApplicationEvaluationSortField.OVERALL_SCORE
            ),
            sort_direction=(
                ApplicationEvaluationSortDirection.ASCENDING
            ),
        )
    )

    assert [
        item.evaluation_id
        for item in page.items
    ] == [
        "evaluation-002",
        "evaluation-003",
        "evaluation-001",
    ]


def test_pagination_and_count() -> None:
    repository = repository_with_records()
    query = ApplicationEvaluationQuery(
        page=2,
        page_size=2,
    )

    page = repository.list(query)

    assert page.total_items == 3
    assert page.total_pages == 2
    assert len(page.items) == 1
    assert repository.count(
        ApplicationEvaluationQuery()
    ) == 3


def test_query_rejects_invalid_score_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "minimum_score must not exceed maximum_score"
        ),
    ):
        ApplicationEvaluationQuery(
            minimum_score=0.9,
            maximum_score=0.5,
        )


def test_query_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="started_from must be timezone-aware",
    ):
        ApplicationEvaluationQuery(
            started_from=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                3,
                40,
            )
        )


def test_clear_removes_records() -> None:
    repository = repository_with_records()

    repository.clear()

    assert repository.count(
        ApplicationEvaluationQuery()
    ) == 0
