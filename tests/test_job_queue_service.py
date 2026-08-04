"""Tests for the application background-job queue service."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.job_queue_service import (
    ApplicationJobQueueService,
)
from app.application.job_queue_service_error import (
    ApplicationJobLeaseExpiredError,
    ApplicationJobLeaseOwnershipError,
    ApplicationJobNotQueueableError,
    ApplicationJobQueueServiceError,
)
from app.application.job_record import (
    ApplicationJobFailure,
    ApplicationJobFailureCategory,
    ApplicationJobLease,
    ApplicationJobPriority,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    4,
    0,
    tzinfo=UTC,
)


def failure() -> ApplicationJobFailure:
    """Return one retryable job failure."""

    return ApplicationJobFailure(
        category=ApplicationJobFailureCategory.TIMEOUT,
        code="JOB_TIMEOUT",
        message="The job timed out.",
        retryable=True,
        retry_reason="The timeout may be temporary.",
    )


def record(
    *,
    job_id: str,
    status: ApplicationJobStatus = (
        ApplicationJobStatus.PENDING
    ),
    priority: ApplicationJobPriority = (
        ApplicationJobPriority.NORMAL
    ),
    available_at: datetime = BASE_TIME,
    created_at: datetime = BASE_TIME,
    lease: ApplicationJobLease | None = None,
    record_version: int = 1,
) -> ApplicationJobRecord:
    """Return one background-job record."""

    values: dict[str, object] = {
        "job_id": job_id,
        "root_job_id": job_id,
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "execution_id": "execution-001",
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": "research",
        "priority": priority,
        "status": status,
        "payload": {
            "assignment_id": "assignment-001",
        },
        "attempt_number": 1,
        "maximum_attempts": 3,
        "available_at": available_at,
        "created_at": created_at,
        "record_version": record_version,
    }

    if status is ApplicationJobStatus.QUEUED:
        values["queued_at"] = created_at

    if status is ApplicationJobStatus.LEASED:
        values["queued_at"] = created_at
        values["lease"] = lease

    if status is ApplicationJobStatus.RUNNING:
        values["queued_at"] = created_at
        values["started_at"] = created_at
        values["lease"] = lease

    if status is ApplicationJobStatus.RETRY_SCHEDULED:
        values["failure"] = failure()

    return ApplicationJobRecord.model_validate(values)


def expired_lease(
    *,
    worker_id: str = "worker-001",
) -> ApplicationJobLease:
    """Return one expired lease."""

    return ApplicationJobLease(
        lease_id="lease-expired",
        worker_id=worker_id,
        acquired_at=BASE_TIME - timedelta(seconds=20),
        expires_at=BASE_TIME - timedelta(seconds=1),
    )


def active_lease(
    *,
    worker_id: str = "worker-001",
) -> ApplicationJobLease:
    """Return one active lease."""

    return ApplicationJobLease(
        lease_id="lease-active",
        worker_id=worker_id,
        acquired_at=BASE_TIME - timedelta(seconds=5),
        expires_at=BASE_TIME + timedelta(seconds=30),
    )


def service(
    records: list[ApplicationJobRecord] | None = None,
) -> tuple[
    ApplicationJobQueueService,
    InMemoryApplicationJobRepository,
]:
    """Return one deterministic queue service."""

    repository = InMemoryApplicationJobRepository(
        records or []
    )

    value = ApplicationJobQueueService(
        repository=repository,
        lease_id_factory=lambda: "lease-001",
    )

    return value, repository


def test_enqueue_pending_job() -> None:
    value, repository = service(
        [record(job_id="job-001")]
    )

    queued = value.enqueue(
        job_id="job-001",
        now=BASE_TIME,
    )

    assert queued.status is ApplicationJobStatus.QUEUED
    assert queued.queued_at == BASE_TIME
    assert queued.record_version == 2
    assert repository.require("job-001") == queued


def test_future_job_cannot_be_enqueued() -> None:
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.SCHEDULED,
                available_at=(
                    BASE_TIME + timedelta(minutes=5)
                ),
            )
        ]
    )

    with pytest.raises(
        ApplicationJobNotQueueableError,
        match=(
            "application job is not available for queueing"
        ),
    ):
        value.enqueue(
            job_id="job-001",
            now=BASE_TIME,
        )


def test_enqueue_due_jobs() -> None:
    value, _ = service(
        [
            record(job_id="job-001"),
            record(
                job_id="job-002",
                status=ApplicationJobStatus.SCHEDULED,
                available_at=BASE_TIME,
            ),
            record(
                job_id="job-future",
                status=ApplicationJobStatus.SCHEDULED,
                available_at=(
                    BASE_TIME + timedelta(minutes=5)
                ),
            ),
        ]
    )

    queued = value.enqueue_due_jobs(now=BASE_TIME)

    assert {
        item.job_id
        for item in queued
    } == {
        "job-001",
        "job-002",
    }


def test_acquire_highest_priority_queued_job() -> None:
    value, _ = service(
        [
            record(
                job_id="job-normal",
                status=ApplicationJobStatus.QUEUED,
                priority=ApplicationJobPriority.NORMAL,
            ),
            record(
                job_id="job-high",
                status=ApplicationJobStatus.QUEUED,
                priority=ApplicationJobPriority.HIGH,
            ),
        ]
    )

    leased = value.acquire(
        queue_name="research",
        worker_id="worker-001",
        now=BASE_TIME,
        lease_duration_seconds=30,
    )

    assert leased is not None
    assert leased.job_id == "job-high"
    assert leased.status is ApplicationJobStatus.LEASED
    assert leased.lease is not None
    assert leased.lease.worker_id == "worker-001"


def test_acquire_returns_none_without_queued_job() -> None:
    value, _ = service(
        [record(job_id="job-pending")]
    )

    leased = value.acquire(
        queue_name="research",
        worker_id="worker-001",
        now=BASE_TIME,
        lease_duration_seconds=30,
    )

    assert leased is None


def test_start_owned_leased_job() -> None:
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.LEASED,
                lease=active_lease(),
            )
        ]
    )

    running = value.start(
        job_id="job-001",
        worker_id="worker-001",
        now=BASE_TIME,
    )

    assert running.status is ApplicationJobStatus.RUNNING
    assert running.started_at == BASE_TIME


def test_start_rejects_different_worker() -> None:
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.LEASED,
                lease=active_lease(),
            )
        ]
    )

    with pytest.raises(
        ApplicationJobLeaseOwnershipError,
        match=(
            "application job lease is owned by another worker"
        ),
    ):
        value.start(
            job_id="job-001",
            worker_id="worker-002",
            now=BASE_TIME,
        )


def test_start_rejects_expired_lease() -> None:
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.LEASED,
                lease=expired_lease(),
            )
        ]
    )

    with pytest.raises(
        ApplicationJobLeaseExpiredError,
        match="application job lease has expired",
    ):
        value.start(
            job_id="job-001",
            worker_id="worker-001",
            now=BASE_TIME,
        )


def test_release_returns_job_to_queue() -> None:
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.LEASED,
                lease=active_lease(),
            )
        ]
    )

    queued = value.release(
        job_id="job-001",
        worker_id="worker-001",
        now=BASE_TIME,
    )

    assert queued.status is ApplicationJobStatus.QUEUED
    assert queued.lease is None


def test_renew_lease_extends_expiry() -> None:
    original_lease = active_lease()
    value, _ = service(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.LEASED,
                lease=original_lease,
            )
        ]
    )

    renewed = value.renew_lease(
        job_id="job-001",
        worker_id="worker-001",
        now=BASE_TIME,
        lease_duration_seconds=60,
    )

    assert renewed.lease is not None
    assert renewed.lease.lease_id == original_lease.lease_id
    assert renewed.lease.expires_at == (
        BASE_TIME + timedelta(seconds=60)
    )


def test_recover_expired_leased_jobs() -> None:
    value, repository = service(
        [
            record(
                job_id="job-expired",
                status=ApplicationJobStatus.LEASED,
                lease=expired_lease(),
            ),
            record(
                job_id="job-active",
                status=ApplicationJobStatus.LEASED,
                lease=active_lease(),
            ),
        ]
    )

    recovered = value.recover_expired_leases(
        now=BASE_TIME
    )

    assert [
        item.job_id
        for item in recovered
    ] == ["job-expired"]

    assert repository.require(
        "job-expired"
    ).status is ApplicationJobStatus.QUEUED

    assert repository.require(
        "job-active"
    ).status is ApplicationJobStatus.LEASED


def test_acquire_rejects_invalid_lease_duration() -> None:
    value, _ = service()

    with pytest.raises(
        ApplicationJobQueueServiceError,
        match=(
            "lease_duration_seconds must be greater than 0"
        ),
    ):
        value.acquire(
            queue_name="research",
            worker_id="worker-001",
            now=BASE_TIME,
            lease_duration_seconds=0,
        )


def test_blank_lease_id_is_rejected() -> None:
    repository = InMemoryApplicationJobRepository(
        [
            record(
                job_id="job-001",
                status=ApplicationJobStatus.QUEUED,
            )
        ]
    )

    value = ApplicationJobQueueService(
        repository=repository,
        lease_id_factory=lambda: " ",
    )

    with pytest.raises(
        ApplicationJobQueueServiceError,
        match="lease_id factory returned blank value",
    ):
        value.acquire(
            queue_name="research",
            worker_id="worker-001",
            now=BASE_TIME,
            lease_duration_seconds=30,
        )


def test_naive_now_is_rejected() -> None:
    value, _ = service()

    with pytest.raises(
        ApplicationJobQueueServiceError,
        match="now must be timezone-aware",
    ):
        value.enqueue_due_jobs(
            now=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                4,
                0,
            )
        )
