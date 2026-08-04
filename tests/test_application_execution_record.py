"""Tests for persistent application execution records."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.execution_record import (
    ApplicationCancellationRecord,
    ApplicationExecutionFailure,
    ApplicationExecutionFailureCategory,
    ApplicationExecutionRecord,
    ApplicationExecutionReference,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.execution_transition import (
    ApplicationExecutionTransitionPolicy,
)

BASE_TIME = datetime(
    2026,
    8,
    4,
    18,
    0,
    tzinfo=UTC,
)


def reference(
    *,
    reference_id: str = "reference-001",
    primary: bool = False,
) -> ApplicationExecutionReference:
    """Return one execution artifact reference."""

    return ApplicationExecutionReference(
        name="research artifact",
        reference_type="research_artifact",
        reference_id=reference_id,
        primary=primary,
    )


def failure(
    *,
    retryable: bool = True,
) -> ApplicationExecutionFailure:
    """Return one execution failure."""

    return ApplicationExecutionFailure(
        category=ApplicationExecutionFailureCategory.TIMEOUT,
        code="EXECUTION_TIMEOUT",
        message="The execution exceeded its timeout.",
        retryable=retryable,
        retry_reason=(
            "The timeout may be transient."
            if retryable
            else None
        ),
    )


def cancellation() -> ApplicationCancellationRecord:
    """Return one persistent cancellation record."""

    return ApplicationCancellationRecord(
        cancellation_id="cancellation-001",
        requested_at=BASE_TIME + timedelta(seconds=2),
        requested_by="user-001",
        reason="The user cancelled the execution.",
    )


def record(
    **overrides: object,
) -> ApplicationExecutionRecord:
    """Return one valid pending execution record."""

    values: dict[str, object] = {
        "execution_id": "execution-001",
        "root_execution_id": "execution-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "subject_type": (
            ApplicationExecutionSubjectType.AGENT
        ),
        "subject_id": "agent-search-001",
        "status": ApplicationExecutionStatus.PENDING,
        "attempt_number": 1,
        "maximum_attempts": 3,
        "inputs": [
            reference(reference_id="question-001"),
        ],
        "created_at": BASE_TIME,
        "record_version": 1,
    }
    values.update(overrides)

    return ApplicationExecutionRecord.model_validate(
        values
    )


def test_pending_execution_record_is_valid() -> None:
    value = record()

    assert value.status is ApplicationExecutionStatus.PENDING
    assert value.terminal is False
    assert value.retry_available is False


def test_running_execution_requires_started_at() -> None:
    with pytest.raises(
        ValidationError,
        match="running execution requires started_at",
    ):
        record(
            status=ApplicationExecutionStatus.RUNNING,
        )


def test_successful_execution_is_terminal() -> None:
    value = record(
        status=ApplicationExecutionStatus.SUCCEEDED,
        started_at=BASE_TIME + timedelta(seconds=1),
        finished_at=BASE_TIME + timedelta(seconds=5),
        outputs=[
            reference(
                reference_id="result-001",
                primary=True,
            )
        ],
    )

    assert value.terminal is True
    assert value.failure is None


@pytest.mark.parametrize(
    "status",
    [
        ApplicationExecutionStatus.FAILED,
        ApplicationExecutionStatus.TIMED_OUT,
    ],
)
def test_failure_status_requires_failure(
    status: ApplicationExecutionStatus,
) -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed or timed-out execution requires failure"
        ),
    ):
        record(
            status=status,
            started_at=BASE_TIME + timedelta(seconds=1),
            finished_at=BASE_TIME + timedelta(seconds=5),
        )


def test_retryable_failed_execution_reports_retry_available() -> None:
    value = record(
        status=ApplicationExecutionStatus.FAILED,
        started_at=BASE_TIME + timedelta(seconds=1),
        finished_at=BASE_TIME + timedelta(seconds=5),
        failure=failure(),
        attempt_number=1,
        maximum_attempts=3,
    )

    assert value.terminal is True
    assert value.retry_available is True


def test_final_attempt_has_no_retry_available() -> None:
    value = record(
        status=ApplicationExecutionStatus.TIMED_OUT,
        started_at=BASE_TIME + timedelta(seconds=1),
        finished_at=BASE_TIME + timedelta(seconds=5),
        failure=failure(),
        attempt_number=3,
        maximum_attempts=3,
        previous_attempt_execution_id="execution-002",
    )

    assert value.retry_available is False


def test_retry_attempt_requires_previous_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry attempt requires "
            "previous_attempt_execution_id"
        ),
    ):
        record(
            attempt_number=2,
        )


def test_first_attempt_rejects_previous_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "first attempt must not include "
            "previous_attempt_execution_id"
        ),
    ):
        record(
            previous_attempt_execution_id="execution-old",
        )


def test_attempt_cannot_exceed_maximum() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "attempt_number must not exceed maximum_attempts"
        ),
    ):
        record(
            attempt_number=4,
            maximum_attempts=3,
            previous_attempt_execution_id="execution-003",
        )


def test_cancellation_requested_requires_record() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "cancellation status requires "
            "cancellation record"
        ),
    ):
        record(
            status=(
                ApplicationExecutionStatus
                .CANCELLATION_REQUESTED
            )
        )


def test_cancelled_execution_is_valid() -> None:
    value = record(
        status=ApplicationExecutionStatus.CANCELLED,
        started_at=BASE_TIME + timedelta(seconds=1),
        finished_at=BASE_TIME + timedelta(seconds=4),
        cancellation=cancellation(),
    )

    assert value.terminal is True


def test_non_cancellation_status_rejects_cancellation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "cancellation record is only valid for "
            "cancellation status"
        ),
    ):
        record(
            cancellation=cancellation(),
        )


def test_duplicate_input_references_are_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="inputs must have unique reference IDs",
    ):
        record(
            inputs=[
                reference(reference_id="INPUT-001"),
                reference(reference_id="input-001"),
            ]
        )


def test_multiple_primary_outputs_are_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "outputs must not contain multiple "
            "primary references"
        ),
    ):
        record(
            outputs=[
                reference(
                    reference_id="output-001",
                    primary=True,
                ),
                reference(
                    reference_id="output-002",
                    primary=True,
                ),
            ]
        )


def test_duplicate_guardrail_ids_are_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "guardrail_evaluation_ids must not "
            "contain duplicates"
        ),
    ):
        record(
            guardrail_evaluation_ids=[
                "GUARDRAIL-001",
                "guardrail-001",
            ]
        )


def test_timestamps_must_be_ordered() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "execution timestamps must be "
            "chronologically ordered"
        ),
    ):
        record(
            status=ApplicationExecutionStatus.RUNNING,
            queued_at=BASE_TIME + timedelta(seconds=5),
            started_at=BASE_TIME + timedelta(seconds=2),
        )


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        record(
            created_at=datetime(  # noqa: DTZ001
                2026,
                8,
                4,
                18,
                0,
            ),
        )


def test_retryable_failure_requires_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retryable failure requires retry_reason"
        ),
    ):
        ApplicationExecutionFailure(
            category=(
                ApplicationExecutionFailureCategory.NETWORK
            ),
            code="NETWORK_ERROR",
            message="Network access failed.",
            retryable=True,
        )


def test_nonretryable_failure_rejects_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "nonretryable failure must not include "
            "retry_reason"
        ),
    ):
        ApplicationExecutionFailure(
            category=(
                ApplicationExecutionFailureCategory.PERMISSION
            ),
            code="PERMISSION_DENIED",
            message="Permission was denied.",
            retryable=False,
            retry_reason="Retry later.",
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (
            ApplicationExecutionStatus.PENDING,
            ApplicationExecutionStatus.QUEUED,
        ),
        (
            ApplicationExecutionStatus.QUEUED,
            ApplicationExecutionStatus.RUNNING,
        ),
        (
            ApplicationExecutionStatus.RUNNING,
            ApplicationExecutionStatus.SUCCEEDED,
        ),
        (
            ApplicationExecutionStatus.RUNNING,
            ApplicationExecutionStatus.FAILED,
        ),
        (
            ApplicationExecutionStatus
            .CANCELLATION_REQUESTED,
            ApplicationExecutionStatus.CANCELLED,
        ),
    ],
)
def test_allowed_status_transitions(
    current: ApplicationExecutionStatus,
    target: ApplicationExecutionStatus,
) -> None:
    assert (
        ApplicationExecutionTransitionPolicy.can_transition(
            current=current,
            target=target,
        )
        is True
    )


def test_terminal_status_cannot_transition() -> None:
    assert (
        ApplicationExecutionTransitionPolicy.can_transition(
            current=ApplicationExecutionStatus.SUCCEEDED,
            target=ApplicationExecutionStatus.RUNNING,
        )
        is False
    )

    with pytest.raises(
        ValueError,
        match=(
            "execution status transition is not allowed: "
            "succeeded -> running"
        ),
    ):
        ApplicationExecutionTransitionPolicy.require_transition(
            current=ApplicationExecutionStatus.SUCCEEDED,
            target=ApplicationExecutionStatus.RUNNING,
        )
