"""Tests for background-job repositories."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
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
from app.application.job_repository_error import (
    ApplicationJobAlreadyExistsError,
    ApplicationJobNotFoundError,
    ApplicationJobVersionConflictError,
)
from app.application.job_repository_query import (
    ApplicationJobQuery,
    ApplicationJobSortDirection,
    ApplicationJobSortField,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    50,
    tzinfo=UTC,
)


def failure() -> ApplicationJobFailure:
    """Return one retryable failure."""

    return ApplicationJobFailure(
        category=ApplicationJobFailureCategory.TIMEOUT,
        code="JOB_TIMEOUT",
        message="The job timed out.",
        retryable=True,
        retry_reason="The timeout may be transient.",
    )


def lease() -> ApplicationJobLease:
    """Return one worker lease."""

    return ApplicationJobLease(
        lease_id="lease-001",
        worker_id="worker-001",
        acquired_at=BASE_TIME,
        expires_at=BASE_TIME + timedelta(seconds=30),
    )


def record(
    *,
    job_id: str,
    queue_name: str = "research",
    status: ApplicationJobStatus = (
        ApplicationJobStatus.PENDING
    ),
    priority: ApplicationJobPriority = (
        ApplicationJobPriority.NORMAL
    ),
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    available_offset: int = 0,
    created_offset: int = 0,
    attempt_number: int = 1,
    maximum_attempts: int = 3,
    previous_attempt_job_id: str | None = None,
    record_version: int = 1,
) -> ApplicationJobRecord:
    """Return one valid job record."""

    values: dict[str, object] = {
        "job_id": job_id,
        "root_job_id": "job-root",
        "request_id": request_id,
        "workspace_id": workspace_id,
        "execution_id": "execution-001",
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": queue_name,
        "priority": priority,
        "status": status,
        "payload": {
            "assignment_id": "assignment-001",
        },
        "attempt_number": attempt_number,
        "maximum_attempts": maximum_attempts,
        "previous_attempt_job_id": previous_attempt_job_id,
        "available_at": (
            BASE_TIME + timedelta(seconds=available_offset)
        ),
        "created_at": (
            BASE_TIME + timedelta(seconds=created_offset)
        ),
        "record_version": record_version,
    }

    if status is ApplicationJobStatus.LEASED:
        values["queued_at"] = values["created_at"]
        values["lease"] = lease()

    if status is ApplicationJobStatus.RUNNING:
        values["queued_at"] = values["created_at"]
        values["started_at"] = values["created_at"]
        values["lease"] = lease()

    if status in {
        ApplicationJobStatus.SUCCEEDED,
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.DEAD_LETTERED,
    }:
        values["queued_at"] = values["created_at"]
        values["started_at"] = values["created_at"]
        values["finished_at"] = (
            values["created_at"] + timedelta(seconds=1)
        )

    if status in {
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.RETRY_SCHEDULED,
        ApplicationJobStatus.DEAD_LETTERED,
    }:
        values["failure"] = failure()

    return ApplicationJobRecord.model_validate(values)


def repository_with_records(
) -> InMemoryApplicationJobRepository:
    """Return one populated job repository."""

    return InMemoryApplicationJobRepository(
        [
            record(
                job_id="job-001",
                priority=ApplicationJobPriority.NORMAL,
                available_offset=0,
                created_offset=-4,
            ),
            record(
                job_id="job-002",
                priority=ApplicationJobPriority.HIGH,
                available_offset=0,
                created_offset=-3,
            ),
            record(
                job_id="job-003",
                priority=ApplicationJobPriority.CRITICAL,
                available_offset=60,
                created_offset=-2,
            ),
            record(
                job_id="job-004",
                queue_name="evaluation",
                priority=ApplicationJobPriority.HIGH,
                available_offset=0,
                created_offset=-1,
            ),
            record(
                job_id="job-005",
                status=ApplicationJobStatus.SUCCEEDED,
                available_offset=0,
                created_offset=0,
            ),
        ]
    )


def test_create_and_case_insensitive_get() -> None:
    repository = InMemoryApplicationJobRepository()
    stored = record(job_id="Job-001")

    repository.create(stored)

    assert repository.get("job-001") == stored
    assert repository.exists("JOB-001") is True


def test_duplicate_job_is_rejected() -> None:
    repository = InMemoryApplicationJobRepository(
        [record(job_id="Job-001")]
    )

    with pytest.raises(
        ApplicationJobAlreadyExistsError,
        match="application job already exists: job-001",
    ):
        repository.create(record(job_id="job-001"))


def test_require_missing_job_fails() -> None:
    repository = InMemoryApplicationJobRepository()

    with pytest.raises(
        ApplicationJobNotFoundError,
        match="application job was not found: job-missing",
    ):
        repository.require("job-missing")


def test_update_uses_optimistic_concurrency() -> None:
    repository = InMemoryApplicationJobRepository()
    original = record(job_id="job-001")
    repository.create(original)

    updated = original.model_copy(
        update={
            "status": ApplicationJobStatus.QUEUED,
            "queued_at": BASE_TIME,
            "record_version": 2,
        }
    )

    value = repository.update(
        updated,
        expected_version=1,
    )

    assert value.record_version == 2
    assert repository.require(
        "job-001"
    ).status is ApplicationJobStatus.QUEUED


def test_update_rejects_stale_version() -> None:
    original = record(
        job_id="job-001",
        record_version=2,
    )
    repository = InMemoryApplicationJobRepository(
        [original]
    )

    updated = original.model_copy(
        update={"record_version": 3}
    )

    with pytest.raises(
        ApplicationJobVersionConflictError,
        match=(
            "application job version conflict: "
            "expected 1, stored 2"
        ),
    ):
        repository.update(
            updated,
            expected_version=1,
        )


def test_default_list_is_created_descending() -> None:
    page = repository_with_records().list(
        ApplicationJobQuery()
    )

    assert [
        item.job_id
        for item in page.items
    ] == [
        "job-005",
        "job-004",
        "job-003",
        "job-002",
        "job-001",
    ]


def test_filter_by_queue_and_status() -> None:
    page = repository_with_records().list(
        ApplicationJobQuery(
            queue_names=["research"],
            statuses=[ApplicationJobStatus.PENDING],
        )
    )

    assert {
        item.job_id
        for item in page.items
    } == {
        "job-001",
        "job-002",
        "job-003",
    }


def test_filter_terminal_jobs() -> None:
    repository = repository_with_records()

    terminal = repository.list(
        ApplicationJobQuery(terminal_only=True)
    )
    nonterminal = repository.list(
        ApplicationJobQuery(terminal_only=False)
    )

    assert [
        item.job_id
        for item in terminal.items
    ] == ["job-005"]

    assert len(nonterminal.items) == 4


def test_sort_priority_descending() -> None:
    page = repository_with_records().list(
        ApplicationJobQuery(
            sort_field=ApplicationJobSortField.PRIORITY,
            sort_direction=(
                ApplicationJobSortDirection.DESCENDING
            ),
        )
    )

    assert page.items[0].priority is (
        ApplicationJobPriority.CRITICAL
    )


def test_find_available_orders_priority_first() -> None:
    jobs = repository_with_records().find_available(
        queue_name="research",
        now=BASE_TIME,
        limit=10,
    )

    assert [
        item.job_id
        for item in jobs
    ] == [
        "job-002",
        "job-001",
    ]


def test_find_available_excludes_future_job() -> None:
    jobs = repository_with_records().find_available(
        queue_name="research",
        now=BASE_TIME,
        limit=10,
    )

    assert "job-003" not in {
        item.job_id
        for item in jobs
    }


def test_find_available_includes_future_job_when_due() -> None:
    jobs = repository_with_records().find_available(
        queue_name="research",
        now=BASE_TIME + timedelta(seconds=60),
        limit=10,
    )

    assert jobs[0].job_id == "job-003"


def test_find_available_excludes_terminal_job() -> None:
    jobs = repository_with_records().find_available(
        queue_name="research",
        now=BASE_TIME + timedelta(minutes=5),
        limit=10,
    )

    assert "job-005" not in {
        item.job_id
        for item in jobs
    }


def test_find_available_respects_limit() -> None:
    jobs = repository_with_records().find_available(
        queue_name="research",
        now=BASE_TIME + timedelta(minutes=5),
        limit=1,
    )

    assert len(jobs) == 1


def test_find_available_rejects_naive_now() -> None:
    with pytest.raises(
        ValueError,
        match="now must be timezone-aware",
    ):
        repository_with_records().find_available(
            queue_name="research",
            now=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                3,
                50,
            ),
        )


def test_query_rejects_duplicate_queue_names() -> None:
    with pytest.raises(
        ValidationError,
        match="queue_names must not contain duplicates",
    ):
        ApplicationJobQuery(
            queue_names=[
                "RESEARCH",
                "research",
            ]
        )


def test_query_rejects_invalid_available_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "available_from must not exceed available_to"
        ),
    ):
        ApplicationJobQuery(
            available_from=BASE_TIME + timedelta(hours=1),
            available_to=BASE_TIME,
        )


def test_pagination_and_count() -> None:
    repository = repository_with_records()

    page = repository.list(
        ApplicationJobQuery(
            page=2,
            page_size=2,
        )
    )

    assert page.total_items == 5
    assert page.total_pages == 3
    assert len(page.items) == 2
    assert repository.count(
        ApplicationJobQuery()
    ) == 5


def test_clear_removes_all_jobs() -> None:
    repository = repository_with_records()

    repository.clear()

    assert repository.count(
        ApplicationJobQuery()
    ) == 0
