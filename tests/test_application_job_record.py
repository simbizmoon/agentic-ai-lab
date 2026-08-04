"""Tests for application background-job records."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.job_record import (
    ApplicationJobCancellation,
    ApplicationJobFailure,
    ApplicationJobFailureCategory,
    ApplicationJobLease,
    ApplicationJobPriority,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.job_transition import (
    ApplicationJobTransitionPolicy,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    40,
    tzinfo=UTC,
)


def failure(
    *,
    retryable: bool = True,
) -> ApplicationJobFailure:
    """Return one job failure."""

    return ApplicationJobFailure(
        category=ApplicationJobFailureCategory.TIMEOUT,
        code="JOB_TIMEOUT",
        message="The background job timed out.",
        retryable=retryable,
        retry_reason=(
            "The failure may be temporary."
            if retryable
            else None
        ),
    )


def lease() -> ApplicationJobLease:
    """Return one active worker lease."""

    return ApplicationJobLease(
        lease_id="lease-001",
        worker_id="worker-001",
        acquired_at=BASE_TIME + timedelta(seconds=2),
        expires_at=BASE_TIME + timedelta(seconds=32),
    )


def cancellation() -> ApplicationJobCancellation:
    """Return one cancellation request."""

    return ApplicationJobCancellation(
        cancellation_id="cancel-001",
        requested_at=BASE_TIME + timedelta(seconds=3),
        requested_by="user-001",
        reason="The user cancelled the job.",
    )


def record(
    **overrides: object,
) -> ApplicationJobRecord:
    """Return one valid pending background job."""

    values: dict[str, object] = {
        "job_id": "job-001",
        "root_job_id": "job-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "execution_id": "execution-001",
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": "research",
        "priority": ApplicationJobPriority.NORMAL,
        "status": ApplicationJobStatus.PENDING,
        "payload": {
            "assignment_id": "assignment-001",
        },
        "attempt_number": 1,
        "maximum_attempts": 3,
        "available_at": BASE_TIME,
        "created_at": BASE_TIME,
        "record_version": 1,
    }
    values.update(overrides)

    return ApplicationJobRecord.model_validate(values)


def test_pending_job_is_valid() -> None:
    value = record()

    assert value.status is ApplicationJobStatus.PENDING
    assert value.terminal is False
    assert value.retry_available is False
    assert value.available_for_queue_at(BASE_TIME) is True


def test_future_scheduled_job_is_not_available() -> None:
    value = record(
        status=ApplicationJobStatus.SCHEDULED,
        available_at=BASE_TIME + timedelta(minutes=5),
    )

    assert value.available_for_queue_at(BASE_TIME) is False
    assert value.available_for_queue_at(
        BASE_TIME + timedelta(minutes=5)
    ) is True


def test_leased_job_requires_lease() -> None:
    with pytest.raises(
        ValidationError,
        match="leased or running job requires lease",
    ):
        record(
            status=ApplicationJobStatus.LEASED,
            queued_at=BASE_TIME + timedelta(seconds=1),
        )


def test_running_job_requires_started_at() -> None:
    with pytest.raises(
        ValidationError,
        match="running job requires started_at",
    ):
        record(
            status=ApplicationJobStatus.RUNNING,
            queued_at=BASE_TIME + timedelta(seconds=1),
            lease=lease(),
        )


def test_running_job_with_lease_is_valid() -> None:
    value = record(
        status=ApplicationJobStatus.RUNNING,
        queued_at=BASE_TIME + timedelta(seconds=1),
        started_at=BASE_TIME + timedelta(seconds=3),
        lease=lease(),
    )

    assert value.terminal is False


def test_successful_job_is_terminal() -> None:
    value = record(
        status=ApplicationJobStatus.SUCCEEDED,
        queued_at=BASE_TIME + timedelta(seconds=1),
        started_at=BASE_TIME + timedelta(seconds=2),
        finished_at=BASE_TIME + timedelta(seconds=5),
    )

    assert value.terminal is True


@pytest.mark.parametrize(
    "status",
    [
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.RETRY_SCHEDULED,
        ApplicationJobStatus.DEAD_LETTERED,
    ],
)
def test_failure_status_requires_failure(
    status: ApplicationJobStatus,
) -> None:
    values: dict[str, object] = {
        "status": status,
    }

    if status in {
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.DEAD_LETTERED,
    }:
        values.update(
            {
                "queued_at": BASE_TIME + timedelta(seconds=1),
                "started_at": BASE_TIME + timedelta(seconds=2),
                "finished_at": BASE_TIME + timedelta(seconds=5),
            }
        )

    with pytest.raises(
        ValidationError,
        match="failure status requires failure information",
    ):
        record(**values)


def test_retry_scheduled_job_is_retry_available() -> None:
    value = record(
        status=ApplicationJobStatus.RETRY_SCHEDULED,
        failure=failure(),
        attempt_number=1,
        maximum_attempts=3,
        available_at=BASE_TIME + timedelta(seconds=10),
    )

    assert value.retry_available is True


def test_retry_scheduled_rejects_final_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry_scheduled job requires another "
            "available attempt"
        ),
    ):
        record(
            status=ApplicationJobStatus.RETRY_SCHEDULED,
            failure=failure(),
            attempt_number=3,
            maximum_attempts=3,
            previous_attempt_job_id="job-002",
        )


def test_retry_attempt_requires_previous_attempt_job() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry attempt requires previous_attempt_job_id"
        ),
    ):
        record(
            attempt_number=2,
        )


def test_first_attempt_rejects_previous_attempt_job() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "first attempt must not include "
            "previous_attempt_job_id"
        ),
    ):
        record(
            previous_attempt_job_id="job-previous",
        )


def test_cancellation_status_requires_information() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "cancellation status requires "
            "cancellation information"
        ),
    ):
        record(
            status=ApplicationJobStatus.CANCELLATION_REQUESTED,
        )


def test_cancelled_job_is_valid() -> None:
    value = record(
        status=ApplicationJobStatus.CANCELLED,
        queued_at=BASE_TIME + timedelta(seconds=1),
        started_at=BASE_TIME + timedelta(seconds=2),
        finished_at=BASE_TIME + timedelta(seconds=4),
        cancellation=cancellation(),
    )

    assert value.terminal is True


def test_lease_reports_active_window() -> None:
    value = lease()

    assert value.active_at(
        BASE_TIME + timedelta(seconds=3)
    ) is True
    assert value.active_at(
        BASE_TIME + timedelta(seconds=32)
    ) is False


def test_lease_rejects_invalid_expiry() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expires_at must be later than acquired_at"
        ),
    ):
        ApplicationJobLease(
            lease_id="lease-invalid",
            worker_id="worker-001",
            acquired_at=BASE_TIME,
            expires_at=BASE_TIME,
        )


def test_available_at_cannot_precede_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "available_at must not precede created_at"
        ),
    ):
        record(
            available_at=BASE_TIME - timedelta(seconds=1),
        )


def test_naive_available_at_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="available_at must be timezone-aware",
    ):
        record(
            available_at=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                3,
                40,
            )
        )


def test_available_for_queue_rejects_naive_now() -> None:
    value = record()

    with pytest.raises(
        ValueError,
        match="now must be timezone-aware",
    ):
        value.available_for_queue_at(
            datetime(2026, 8, 5, 3, 40)  # noqa: DTZ001
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (
            ApplicationJobStatus.PENDING,
            ApplicationJobStatus.SCHEDULED,
        ),
        (
            ApplicationJobStatus.SCHEDULED,
            ApplicationJobStatus.QUEUED,
        ),
        (
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.LEASED,
        ),
        (
            ApplicationJobStatus.LEASED,
            ApplicationJobStatus.RUNNING,
        ),
        (
            ApplicationJobStatus.RUNNING,
            ApplicationJobStatus.SUCCEEDED,
        ),
        (
            ApplicationJobStatus.RUNNING,
            ApplicationJobStatus.RETRY_SCHEDULED,
        ),
        (
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        ),
    ],
)
def test_allowed_job_transitions(
    current: ApplicationJobStatus,
    target: ApplicationJobStatus,
) -> None:
    assert (
        ApplicationJobTransitionPolicy.can_transition(
            current=current,
            target=target,
        )
        is True
    )


def test_terminal_job_cannot_transition() -> None:
    assert (
        ApplicationJobTransitionPolicy.can_transition(
            current=ApplicationJobStatus.SUCCEEDED,
            target=ApplicationJobStatus.RUNNING,
        )
        is False
    )

    with pytest.raises(
        ValueError,
        match=(
            "job status transition is not allowed: "
            "succeeded -> running"
        ),
    ):
        ApplicationJobTransitionPolicy.require_transition(
            current=ApplicationJobStatus.SUCCEEDED,
            target=ApplicationJobStatus.RUNNING,
        )
