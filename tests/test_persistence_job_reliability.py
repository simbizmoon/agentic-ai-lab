"""Persistence and background-job reliability tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.cancellation_record import (
    ApplicationCancellationStatus,
)
from app.application.cancellation_service import (
    ApplicationCancellationService,
)
from app.application.idempotency_record import (
    ApplicationIdempotencyStatus,
)
from app.application.idempotency_service import (
    ApplicationIdempotencyService,
    ApplicationIdempotencyStartRequest,
)
from app.application.in_memory_cancellation_repository import (
    InMemoryApplicationCancellationRepository,
)
from app.application.in_memory_idempotency_repository import (
    InMemoryApplicationIdempotencyRepository,
)
from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.in_memory_transaction_manager import (
    InMemoryApplicationTransactionManager,
)
from app.application.job_queue_service import (
    ApplicationJobQueueService,
)
from app.application.job_record import (
    ApplicationJobFailure,
    ApplicationJobFailureCategory,
    ApplicationJobPriority,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.retry_scheduling_service import (
    ApplicationRetrySchedulingService,
)
from app.guardrails.retry_decision import (
    RetryFailureContext,
)
from app.guardrails.retry_policy import (
    RetryBackoffStrategy,
    RetryFailureCategory,
    RetryJitterStrategy,
    RetryPolicy,
)
from app.guardrails.retry_policy_evaluator import (
    RetryPolicyEvaluator,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    6,
    10,
    tzinfo=UTC,
)


class IncrementingClock:
    """Return deterministic increasing timestamps."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> datetime:
        value = BASE_TIME + timedelta(
            seconds=self._calls
        )
        self._calls += 1
        return value


def pending_job(
    *,
    job_id: str = "job-001",
    available_at: datetime = BASE_TIME,
) -> ApplicationJobRecord:
    """Return one pending application job."""

    return ApplicationJobRecord(
        job_id=job_id,
        root_job_id=job_id,
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id="execution-001",
        job_type=ApplicationJobType.AGENT_EXECUTION,
        queue_name="research",
        priority=ApplicationJobPriority.HIGH,
        status=ApplicationJobStatus.PENDING,
        payload={
            "query": "grounded research agents",
        },
        attempt_number=1,
        maximum_attempts=3,
        available_at=available_at,
        created_at=BASE_TIME,
        record_version=1,
    )


def failed_job(
    *,
    job_id: str = "job-attempt-001",
) -> ApplicationJobRecord:
    """Return one retryable failed job."""

    return ApplicationJobRecord(
        job_id=job_id,
        root_job_id="job-root-001",
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id="execution-001",
        job_type=ApplicationJobType.AGENT_EXECUTION,
        queue_name="research",
        priority=ApplicationJobPriority.HIGH,
        status=ApplicationJobStatus.FAILED,
        payload={
            "query": "grounded research agents",
        },
        attempt_number=1,
        maximum_attempts=3,
        available_at=BASE_TIME - timedelta(seconds=20),
        created_at=BASE_TIME - timedelta(seconds=20),
        queued_at=BASE_TIME - timedelta(seconds=15),
        started_at=BASE_TIME - timedelta(seconds=10),
        finished_at=BASE_TIME - timedelta(seconds=1),
        failure=ApplicationJobFailure(
            category=ApplicationJobFailureCategory.TIMEOUT,
            code="JOB_TIMEOUT",
            message="The background job timed out.",
            retryable=True,
            retry_reason="The timeout may be temporary.",
        ),
        record_version=1,
    )


def retry_policy() -> RetryPolicy:
    """Return one deterministic retry policy."""

    return RetryPolicy(
        policy_id="job-retry-policy",
        name="Job retry policy",
        description="Retry temporary job failures.",
        version="1.0.0",
        maximum_attempts=3,
        base_delay_seconds=5.0,
        maximum_delay_seconds=60.0,
        backoff_strategy=RetryBackoffStrategy.EXPONENTIAL,
        multiplier=2.0,
        jitter_strategy=RetryJitterStrategy.NONE,
        allowed_categories=[
            RetryFailureCategory.TIMEOUT,
        ],
        denied_categories=[
            RetryFailureCategory.VALIDATION,
            RetryFailureCategory.PERMISSION,
        ],
        respect_retry_after=True,
        retry_after_max_seconds=120.0,
    )


def retry_failure() -> RetryFailureContext:
    """Return one retry evaluation failure."""

    return RetryFailureContext(
        failure_id="failure-001",
        category=RetryFailureCategory.TIMEOUT,
        error_code="JOB_TIMEOUT",
        message="The background job timed out.",
        retryable=True,
        attempt_number=1,
    )


def test_transaction_rolls_back_job_and_idempotency() -> None:
    jobs = InMemoryApplicationJobRepository()
    idempotency = (
        InMemoryApplicationIdempotencyRepository()
    )

    idempotency_service = ApplicationIdempotencyService(
        repository=idempotency,
        clock=IncrementingClock(),
        record_id_factory=lambda: "idempotency-001",
    )

    manager = InMemoryApplicationTransactionManager(
        resources=[
            jobs,
            idempotency,
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="simulated persistence failure",
    ), manager.transaction():
        jobs.create(pending_job())

        idempotency_service.begin(
            ApplicationIdempotencyStartRequest(
                workspace_id="workspace-001",
                operation="research.execute",
                idempotency_key="research-key-001",
                payload={
                    "query": "grounded research agents",
                },
            )
        )

        raise RuntimeError(
            "simulated persistence failure"
        )

    assert jobs.exists("job-001") is False
    assert idempotency.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
    ) is None


def test_expired_job_lease_is_recovered_to_queue() -> None:
    repository = InMemoryApplicationJobRepository(
        [pending_job()]
    )

    queue = ApplicationJobQueueService(
        repository=repository,
        lease_id_factory=lambda: "lease-001",
    )

    queued = queue.enqueue(
        job_id="job-001",
        now=BASE_TIME,
    )

    assert queued.status is ApplicationJobStatus.QUEUED

    leased = queue.acquire(
        queue_name="research",
        worker_id="worker-001",
        now=BASE_TIME,
        lease_duration_seconds=5.0,
    )

    assert leased is not None
    assert leased.status is ApplicationJobStatus.LEASED
    assert leased.lease is not None

    recovered = queue.recover_expired_leases(
        now=BASE_TIME + timedelta(seconds=6),
        queue_name="research",
    )

    assert len(recovered) == 1
    assert recovered[0].status is ApplicationJobStatus.QUEUED
    assert recovered[0].lease is None

    stored = repository.require("job-001")

    assert stored.status is ApplicationJobStatus.QUEUED
    assert stored.lease is None


def test_active_lease_is_not_recovered_early() -> None:
    repository = InMemoryApplicationJobRepository(
        [pending_job()]
    )

    queue = ApplicationJobQueueService(
        repository=repository,
        lease_id_factory=lambda: "lease-001",
    )

    queue.enqueue(
        job_id="job-001",
        now=BASE_TIME,
    )

    queue.acquire(
        queue_name="research",
        worker_id="worker-001",
        now=BASE_TIME,
        lease_duration_seconds=10.0,
    )

    recovered = queue.recover_expired_leases(
        now=BASE_TIME + timedelta(seconds=9),
        queue_name="research",
    )

    assert recovered == []

    stored = repository.require("job-001")

    assert stored.status is ApplicationJobStatus.LEASED
    assert stored.lease is not None


def test_failed_job_retry_is_scheduled_and_enqueued() -> None:
    source = failed_job()
    repository = InMemoryApplicationJobRepository(
        [source]
    )

    retry_service = ApplicationRetrySchedulingService(
        job_repository=repository,
        retry_policy_evaluator=RetryPolicyEvaluator(
            policy=retry_policy(),
            decision_id_factory=(
                lambda: "retry-decision-001"
            ),
            random_fraction_factory=lambda: 0.5,
        ),
        job_id_factory=lambda: "job-attempt-002",
        scheduling_id_factory=(
            lambda: "retry-scheduling-001"
        ),
    )

    scheduled_result = retry_service.schedule(
        source_job_id=source.job_id,
        failure=retry_failure(),
        now=BASE_TIME,
    )

    scheduled = scheduled_result.scheduled_job

    assert scheduled is not None
    assert scheduled.status is (
        ApplicationJobStatus.SCHEDULED
    )
    assert scheduled.attempt_number == 2
    assert scheduled.previous_attempt_job_id == source.job_id
    assert scheduled.available_at == (
        BASE_TIME + timedelta(seconds=5)
    )

    queue = ApplicationJobQueueService(
        repository=repository
    )

    too_early = queue.enqueue_due_jobs(
        now=BASE_TIME + timedelta(seconds=4),
        queue_name="research",
    )

    assert too_early == []

    due = queue.enqueue_due_jobs(
        now=BASE_TIME + timedelta(seconds=5),
        queue_name="research",
    )

    assert len(due) == 1
    assert due[0].job_id == "job-attempt-002"
    assert due[0].status is ApplicationJobStatus.QUEUED


def test_cancellation_commit_persists_both_records() -> None:
    jobs = InMemoryApplicationJobRepository(
        [pending_job()]
    )
    cancellations = (
        InMemoryApplicationCancellationRepository()
    )

    service = ApplicationCancellationService(
        job_repository=jobs,
        cancellation_repository=cancellations,
        cancellation_id_factory=(
            lambda: "cancellation-001"
        ),
    )

    manager = InMemoryApplicationTransactionManager(
        resources=[
            jobs,
            cancellations,
        ]
    )

    with manager.transaction():
        cancellation = service.request(
            job_id="job-001",
            requested_by="user-001",
            reason="The research is no longer needed.",
            now=BASE_TIME,
        )

    assert cancellation.status is (
        ApplicationCancellationStatus.REQUESTED
    )

    stored_job = jobs.require("job-001")
    stored_cancellation = cancellations.require(
        "cancellation-001"
    )

    assert stored_job.status is (
        ApplicationJobStatus.CANCELLATION_REQUESTED
    )
    assert stored_job.cancellation is not None
    assert stored_cancellation == cancellation


def test_cancellation_transaction_failure_rolls_back() -> None:
    original = pending_job()
    jobs = InMemoryApplicationJobRepository([original])
    cancellations = (
        InMemoryApplicationCancellationRepository()
    )

    service = ApplicationCancellationService(
        job_repository=jobs,
        cancellation_repository=cancellations,
        cancellation_id_factory=(
            lambda: "cancellation-001"
        ),
    )

    manager = InMemoryApplicationTransactionManager(
        resources=[
            jobs,
            cancellations,
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="failure after cancellation request",
    ), manager.transaction():
        service.request(
            job_id="job-001",
            requested_by="user-001",
            reason="Cancel this job.",
            now=BASE_TIME,
        )

        raise RuntimeError(
            "failure after cancellation request"
        )

    assert jobs.require("job-001") == original
    assert cancellations.get("cancellation-001") is None


def test_successful_idempotency_result_is_reused() -> None:
    repository = (
        InMemoryApplicationIdempotencyRepository()
    )
    service = ApplicationIdempotencyService(
        repository=repository,
        clock=IncrementingClock(),
        record_id_factory=lambda: "idempotency-001",
    )

    request = ApplicationIdempotencyStartRequest(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
        payload={
            "query": "grounded research agents",
            "limit": 5,
        },
    )

    first = service.begin(request)

    completed = service.succeed(
        idempotency_record_id=(
            first.record.idempotency_record_id
        ),
        result={
            "execution_id": "execution-001",
            "status": "succeeded",
        },
    )

    duplicate = service.begin(request)

    assert completed.status is (
        ApplicationIdempotencyStatus.SUCCEEDED
    )
    assert duplicate.execute_operation is False
    assert duplicate.reused_result == {
        "execution_id": "execution-001",
        "status": "succeeded",
    }
    assert repository.require(
        "idempotency-001"
    ).record_version == 2


def test_idempotency_snapshot_restores_secondary_index() -> None:
    repository = (
        InMemoryApplicationIdempotencyRepository()
    )
    service = ApplicationIdempotencyService(
        repository=repository,
        clock=IncrementingClock(),
        record_id_factory=lambda: "idempotency-001",
    )

    request = ApplicationIdempotencyStartRequest(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
        payload={
            "query": "grounded research agents",
        },
    )

    service.begin(request)
    snapshot = repository.snapshot_state()

    repository.restore_state(({}, {}))

    assert repository.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
    ) is None

    repository.restore_state(snapshot)

    restored = repository.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
    )

    assert restored is not None
    assert restored.idempotency_record_id == (
        "idempotency-001"
    )
