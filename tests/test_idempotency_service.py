"""Tests for application idempotency and duplicate prevention."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.idempotency_record import (
    ApplicationIdempotencyStatus,
)
from app.application.idempotency_service import (
    ApplicationIdempotencyService,
    ApplicationIdempotencyStartRequest,
)
from app.application.idempotency_service_error import (
    ApplicationIdempotencyConflictError,
    ApplicationIdempotencyInProgressError,
    ApplicationIdempotencyRetryNotAllowedError,
    ApplicationIdempotencyServiceError,
)
from app.application.in_memory_idempotency_repository import (
    InMemoryApplicationIdempotencyRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    5,
    30,
    tzinfo=UTC,
)


class IncrementingClock:
    """Return increasing timestamps."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> datetime:
        value = BASE_TIME + timedelta(seconds=self._calls)
        self._calls += 1
        return value


def request(
    *,
    payload: object | None = None,
) -> ApplicationIdempotencyStartRequest:
    """Return one valid start request."""

    return ApplicationIdempotencyStartRequest(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="request-key-001",
        payload=(
            payload
            if payload is not None
            else {
                "query": "grounded agents",
                "limit": 5,
            }
        ),
        metadata={"source": "api"},
    )


def service() -> tuple[
    ApplicationIdempotencyService,
    InMemoryApplicationIdempotencyRepository,
]:
    """Return deterministic idempotency infrastructure."""

    repository = InMemoryApplicationIdempotencyRepository()

    value = ApplicationIdempotencyService(
        repository=repository,
        clock=IncrementingClock(),
        record_id_factory=lambda: "idempotency-001",
    )

    return value, repository


def test_first_request_starts_operation() -> None:
    value, repository = service()

    result = value.begin(request())

    assert result.execute_operation is True
    assert result.reused_result is None
    assert result.record.status is (
        ApplicationIdempotencyStatus.IN_PROGRESS
    )
    assert repository.require(
        "idempotency-001"
    ) == result.record


def test_successful_duplicate_reuses_result() -> None:
    value, _ = service()

    started = value.begin(request())

    value.succeed(
        idempotency_record_id=(
            started.record.idempotency_record_id
        ),
        result={
            "execution_id": "execution-001",
            "status": "succeeded",
        },
    )

    duplicate = value.begin(request())

    assert duplicate.execute_operation is False
    assert duplicate.reused_result == {
        "execution_id": "execution-001",
        "status": "succeeded",
    }


def test_in_progress_duplicate_is_rejected() -> None:
    value, _ = service()

    value.begin(request())

    with pytest.raises(
        ApplicationIdempotencyInProgressError,
        match="already in progress",
    ):
        value.begin(request())


def test_different_payload_conflicts() -> None:
    value, _ = service()

    value.begin(request())

    with pytest.raises(
        ApplicationIdempotencyConflictError,
        match="different request payload",
    ):
        value.begin(
            request(
                payload={
                    "query": "different query",
                    "limit": 5,
                }
            )
        )


def test_failed_operation_can_restart() -> None:
    value, repository = service()

    started = value.begin(request())

    failed = value.fail(
        idempotency_record_id=(
            started.record.idempotency_record_id
        ),
        code="PROVIDER_ERROR",
        message="Provider unavailable.",
        retryable=True,
    )

    restarted = value.begin(request())

    assert failed.status is ApplicationIdempotencyStatus.FAILED
    assert restarted.execute_operation is True
    assert restarted.record.status is (
        ApplicationIdempotencyStatus.IN_PROGRESS
    )
    assert restarted.record.record_version == 3
    assert restarted.record.failure is None
    assert repository.require(
        "idempotency-001"
    ) == restarted.record


def test_failed_operation_retry_can_be_disabled() -> None:
    value, _ = service()

    started = value.begin(request())

    value.fail(
        idempotency_record_id=(
            started.record.idempotency_record_id
        ),
        code="VALIDATION_ERROR",
        message="Invalid input.",
        retryable=False,
    )

    with pytest.raises(
        ApplicationIdempotencyRetryNotAllowedError,
        match="cannot be retried",
    ):
        value.begin(
            request(),
            allow_retry_after_failure=False,
        )


def test_succeed_requires_in_progress_record() -> None:
    value, _ = service()

    started = value.begin(request())

    value.succeed(
        idempotency_record_id=(
            started.record.idempotency_record_id
        ),
        result={"status": "ok"},
    )

    with pytest.raises(
        ApplicationIdempotencyServiceError,
        match="only in-progress operation may succeed",
    ):
        value.succeed(
            idempotency_record_id=(
                started.record.idempotency_record_id
            ),
            result={"status": "ok"},
        )


def test_fingerprint_is_stable_for_key_order() -> None:
    first = ApplicationIdempotencyService.fingerprint(
        {"a": 1, "b": 2}
    )
    second = ApplicationIdempotencyService.fingerprint(
        {"b": 2, "a": 1}
    )

    assert first == second
    assert len(first) == 64


def test_repository_snapshot_restores_identity_index() -> None:
    value, repository = service()

    value.begin(request())
    snapshot = repository.snapshot_state()

    repository.restore_state(({}, {}))

    assert repository.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="request-key-001",
    ) is None

    repository.restore_state(snapshot)

    assert repository.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="request-key-001",
    ) is not None


def test_naive_clock_is_rejected() -> None:
    value = ApplicationIdempotencyService(
        repository=(
            InMemoryApplicationIdempotencyRepository()
        ),
        clock=lambda: datetime(  # noqa: DTZ001
            2026,
            8,
            5,
            5,
            30,
        ),
        record_id_factory=lambda: "idempotency-001",
    )

    with pytest.raises(
        ApplicationIdempotencyServiceError,
        match="clock must return timezone-aware datetime",
    ):
        value.begin(request())
