"""Tests for application retry scheduling."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.job_record import (
    ApplicationJobFailure,
    ApplicationJobFailureCategory,
    ApplicationJobPriority,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.job_repository_query import (
    ApplicationJobQuery,
)
from app.application.retry_scheduling_result import (
    ApplicationRetrySchedulingStatus,
)
from app.application.retry_scheduling_service import (
    ApplicationRetrySchedulingService,
)
from app.application.retry_scheduling_service_error import (
    ApplicationJobNotRetryableError,
    ApplicationRetryAlreadyScheduledError,
    ApplicationRetrySchedulingServiceError,
)
from app.guardrails.retry_decision import (
    RetryDecisionType,
    RetryFailureContext,
    RetryStopReason,
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
    4,
    10,
    tzinfo=UTC,
)


def retry_policy(
    *,
    maximum_attempts: int = 3,
    base_delay_seconds: float = 5.0,
) -> RetryPolicy:
    """Return one deterministic retry policy."""

    return RetryPolicy(
        policy_id="job-retry-policy",
        name="Job retry policy",
        description="Retry temporary background-job failures.",
        version="1.0.0",
        maximum_attempts=maximum_attempts,
        base_delay_seconds=base_delay_seconds,
        maximum_delay_seconds=60.0,
        backoff_strategy=RetryBackoffStrategy.EXPONENTIAL,
        multiplier=2.0,
        jitter_strategy=RetryJitterStrategy.NONE,
        allowed_categories=[
            RetryFailureCategory.TIMEOUT,
            RetryFailureCategory.NETWORK,
        ],
        denied_categories=[
            RetryFailureCategory.VALIDATION,
            RetryFailureCategory.PERMISSION,
        ],
        respect_retry_after=True,
        retry_after_max_seconds=120.0,
    )


def job_failure(
    *,
    retryable: bool = True,
) -> ApplicationJobFailure:
    """Return one persistent job failure."""

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


def source_job(
    *,
    job_id: str = "job-attempt-001",
    status: ApplicationJobStatus = (
        ApplicationJobStatus.FAILED
    ),
    attempt_number: int = 1,
    maximum_attempts: int = 3,
    previous_attempt_job_id: str | None = None,
    failure: ApplicationJobFailure | None = None,
) -> ApplicationJobRecord:
    """Return one failed source job."""

    values: dict[str, object] = {
        "job_id": job_id,
        "root_job_id": "job-root-001",
        "previous_attempt_job_id": (
            previous_attempt_job_id
        ),
        "parent_job_id": "job-parent-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "execution_id": "execution-001",
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": "research",
        "priority": ApplicationJobPriority.HIGH,
        "status": status,
        "payload": {
            "assignment_id": "assignment-001",
        },
        "attempt_number": attempt_number,
        "maximum_attempts": maximum_attempts,
        "available_at": BASE_TIME - timedelta(seconds=20),
        "created_at": BASE_TIME - timedelta(seconds=20),
        "queued_at": BASE_TIME - timedelta(seconds=15),
        "started_at": BASE_TIME - timedelta(seconds=10),
        "finished_at": BASE_TIME - timedelta(seconds=1),
        "record_version": 1,
        "metadata": {
            "source": "research-service",
        },
    }

    if status is ApplicationJobStatus.FAILED:
        values["failure"] = failure or job_failure()

    return ApplicationJobRecord.model_validate(values)


def retry_failure(
    *,
    attempt_number: int = 1,
    retryable: bool = True,
) -> RetryFailureContext:
    """Return one retry evaluation failure."""

    return RetryFailureContext(
        failure_id="failure-001",
        category=RetryFailureCategory.TIMEOUT,
        error_code="JOB_TIMEOUT",
        message="The background job timed out.",
        retryable=retryable,
        attempt_number=attempt_number,
    )


def service(
    *,
    records: list[ApplicationJobRecord] | None = None,
    policy: RetryPolicy | None = None,
) -> tuple[
    ApplicationRetrySchedulingService,
    InMemoryApplicationJobRepository,
]:
    """Return one deterministic scheduling service."""

    stored_records = records or []
    repository = InMemoryApplicationJobRepository(
        stored_records
    )

    next_attempt_number = (
        max(
            (
                record.attempt_number
                for record in stored_records
            ),
            default=1,
        )
        + 1
    )

    evaluator = RetryPolicyEvaluator(
        policy=policy or retry_policy(),
        decision_id_factory=lambda: "retry-decision-001",
        random_fraction_factory=lambda: 0.5,
    )

    value = ApplicationRetrySchedulingService(
        job_repository=repository,
        retry_policy_evaluator=evaluator,
        job_id_factory=(
            lambda: f"job-attempt-{next_attempt_number:03d}"
        ),
        scheduling_id_factory=(
            lambda: "retry-scheduling-001"
        ),
    )

    return value, repository


def test_schedules_next_attempt() -> None:
    source = source_job()
    value, repository = service(records=[source])

    result = value.schedule(
        source_job_id=source.job_id,
        failure=retry_failure(),
        now=BASE_TIME,
    )

    assert result.status is (
        ApplicationRetrySchedulingStatus.SCHEDULED
    )
    assert result.retry_decision.decision is (
        RetryDecisionType.RETRY
    )
    assert result.scheduled_job is not None

    scheduled = result.scheduled_job

    assert scheduled.job_id == "job-attempt-002"
    assert scheduled.root_job_id == source.root_job_id
    assert scheduled.parent_job_id == source.parent_job_id
    assert (
        scheduled.previous_attempt_job_id
        == source.job_id
    )
    assert scheduled.attempt_number == 2
    assert scheduled.maximum_attempts == 3
    assert scheduled.status is ApplicationJobStatus.SCHEDULED
    assert scheduled.available_at == (
        BASE_TIME + timedelta(seconds=5)
    )
    assert scheduled.job_type is (
        ApplicationJobType.RETRY_EXECUTION
    )
    assert repository.require(
        "job-attempt-002"
    ) == scheduled


def test_second_failure_uses_exponential_delay() -> None:
    source = source_job(
        job_id="job-attempt-002",
        attempt_number=2,
        maximum_attempts=3,
        previous_attempt_job_id="job-attempt-001",
    )

    value, _ = service(records=[source])

    result = value.schedule(
        source_job_id=source.job_id,
        failure=retry_failure(attempt_number=2),
        now=BASE_TIME,
    )

    assert result.scheduled_job is not None
    assert result.scheduled_job.attempt_number == 3
    assert result.scheduled_job.available_at == (
        BASE_TIME + timedelta(seconds=10)
    )


def test_final_attempt_stops_without_new_job() -> None:
    source = source_job(
        job_id="job-attempt-003",
        attempt_number=3,
        maximum_attempts=3,
        previous_attempt_job_id="job-attempt-002",
    )

    value, repository = service(records=[source])

    result = value.schedule(
        source_job_id=source.job_id,
        failure=retry_failure(attempt_number=3),
        now=BASE_TIME,
    )

    assert result.status is (
        ApplicationRetrySchedulingStatus.STOPPED
    )
    assert result.retry_decision.decision is (
        RetryDecisionType.STOP
    )
    assert result.retry_decision.stop_reason is (
        RetryStopReason.MAXIMUM_ATTEMPTS_REACHED
    )
    assert result.scheduled_job is None
    assert repository.count(
        ApplicationJobQuery()
    ) == 1


def test_non_failed_job_is_rejected() -> None:
    pending = ApplicationJobRecord(
        job_id="job-pending",
        root_job_id="job-pending",
        request_id="research-001",
        workspace_id="workspace-001",
        job_type=ApplicationJobType.AGENT_EXECUTION,
        queue_name="research",
        status=ApplicationJobStatus.PENDING,
        available_at=BASE_TIME,
        created_at=BASE_TIME,
    )

    value, _ = service(records=[pending])

    with pytest.raises(
        ApplicationJobNotRetryableError,
        match="retry scheduling requires a failed job",
    ):
        value.schedule(
            source_job_id=pending.job_id,
            failure=retry_failure(),
            now=BASE_TIME,
        )


def test_nonretryable_source_failure_is_rejected() -> None:
    source = source_job(
        failure=job_failure(retryable=False)
    )
    value, _ = service(records=[source])

    with pytest.raises(
        ApplicationJobNotRetryableError,
        match="source job failure is not retryable",
    ):
        value.schedule(
            source_job_id=source.job_id,
            failure=retry_failure(retryable=False),
            now=BASE_TIME,
        )


def test_attempt_mismatch_is_rejected() -> None:
    source = source_job()
    value, _ = service(records=[source])

    with pytest.raises(
        ApplicationRetrySchedulingServiceError,
        match=(
            "retry failure attempt_number does not match "
            "the source job"
        ),
    ):
        value.schedule(
            source_job_id=source.job_id,
            failure=retry_failure(attempt_number=2),
            now=BASE_TIME,
        )


def test_duplicate_retry_scheduling_is_rejected() -> None:
    source = source_job()
    existing_retry = ApplicationJobRecord(
        job_id="job-existing-retry",
        root_job_id=source.root_job_id,
        parent_job_id=source.parent_job_id,
        previous_attempt_job_id=source.job_id,
        request_id=source.request_id,
        workspace_id=source.workspace_id,
        execution_id=source.execution_id,
        job_type=ApplicationJobType.RETRY_EXECUTION,
        queue_name=source.queue_name,
        priority=source.priority,
        status=ApplicationJobStatus.SCHEDULED,
        payload=dict(source.payload),
        attempt_number=2,
        maximum_attempts=3,
        available_at=BASE_TIME + timedelta(seconds=5),
        created_at=BASE_TIME,
    )

    value, _ = service(
        records=[source, existing_retry]
    )

    with pytest.raises(
        ApplicationRetryAlreadyScheduledError,
        match=(
            "retry attempt already exists for source job"
        ),
    ):
        value.schedule(
            source_job_id=source.job_id,
            failure=retry_failure(),
            now=BASE_TIME,
        )


def test_retry_after_controls_available_time() -> None:
    source = source_job()
    value, _ = service(records=[source])

    failure = retry_failure().model_copy(
        update={"retry_after_seconds": 20.0}
    )

    result = value.schedule(
        source_job_id=source.job_id,
        failure=failure,
        now=BASE_TIME,
    )

    assert result.scheduled_job is not None
    assert result.scheduled_job.available_at == (
        BASE_TIME + timedelta(seconds=20)
    )


def test_zero_delay_creates_pending_job() -> None:
    source = source_job()
    value, _ = service(
        records=[source],
        policy=retry_policy(base_delay_seconds=0.0),
    )

    result = value.schedule(
        source_job_id=source.job_id,
        failure=retry_failure(),
        now=BASE_TIME,
    )

    assert result.scheduled_job is not None
    assert result.scheduled_job.status is (
        ApplicationJobStatus.PENDING
    )
    assert result.scheduled_job.available_at == BASE_TIME


def test_blank_job_id_factory_is_rejected() -> None:
    source = source_job()
    repository = InMemoryApplicationJobRepository([source])

    value = ApplicationRetrySchedulingService(
        job_repository=repository,
        retry_policy_evaluator=RetryPolicyEvaluator(
            policy=retry_policy(),
        ),
        job_id_factory=lambda: " ",
        scheduling_id_factory=lambda: "scheduling-001",
    )

    with pytest.raises(
        ApplicationRetrySchedulingServiceError,
        match="job_id factory returned blank value",
    ):
        value.schedule(
            source_job_id=source.job_id,
            failure=retry_failure(),
            now=BASE_TIME,
        )


def test_naive_now_is_rejected() -> None:
    value, _ = service()

    with pytest.raises(
        ApplicationRetrySchedulingServiceError,
        match="now must be timezone-aware",
    ):
        value.schedule(
            source_job_id="job-001",
            failure=retry_failure(),
            now=datetime(2026, 8, 5, 4, 10),  # noqa: DTZ001
        )
