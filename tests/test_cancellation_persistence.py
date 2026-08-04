"""Tests for persisted background-job cancellation."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.cancellation_record import (
    ApplicationCancellationStatus,
    ApplicationJobCancellationRequestRecord,
)
from app.application.cancellation_repository_error import (
    ApplicationCancellationAlreadyExistsError,
    ApplicationCancellationVersionConflictError,
)
from app.application.cancellation_service import (
    ApplicationCancellationService,
)
from app.application.cancellation_service_error import (
    ApplicationCancellationAlreadyActiveError,
    ApplicationCancellationServiceError,
    ApplicationCancellationStateError,
    ApplicationJobCannotBeCancelledError,
)
from app.application.in_memory_cancellation_repository import (
    InMemoryApplicationCancellationRepository,
)
from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.job_record import (
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    4,
    20,
    tzinfo=UTC,
)


def job(
    *,
    job_id: str = "job-001",
    status: ApplicationJobStatus = (
        ApplicationJobStatus.PENDING
    ),
) -> ApplicationJobRecord:
    """Return one cancellable application job."""

    values: dict[str, object] = {
        "job_id": job_id,
        "root_job_id": job_id,
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": "research",
        "status": status,
        "available_at": BASE_TIME,
        "created_at": BASE_TIME,
    }

    if status is ApplicationJobStatus.SUCCEEDED:
        values.update(
            {
                "queued_at": BASE_TIME,
                "started_at": BASE_TIME,
                "finished_at": (
                    BASE_TIME + timedelta(seconds=1)
                ),
            }
        )

    return ApplicationJobRecord.model_validate(values)


def cancellation_record(
    *,
    cancellation_request_id: str = "cancellation-001",
    job_id: str = "job-001",
    status: ApplicationCancellationStatus = (
        ApplicationCancellationStatus.REQUESTED
    ),
    record_version: int = 1,
) -> ApplicationJobCancellationRequestRecord:
    """Return one persisted cancellation request."""

    values: dict[str, object] = {
        "cancellation_request_id": (
            cancellation_request_id
        ),
        "job_id": job_id,
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "requested_by": "user-001",
        "reason": "The user cancelled the job.",
        "status": status,
        "requested_at": BASE_TIME,
        "record_version": record_version,
    }

    if status in {
        ApplicationCancellationStatus.ACKNOWLEDGED,
        ApplicationCancellationStatus.COMPLETED,
    }:
        values.update(
            {
                "acknowledged_at": (
                    BASE_TIME + timedelta(seconds=1)
                ),
                "acknowledged_by": "worker-001",
            }
        )

    if status is ApplicationCancellationStatus.COMPLETED:
        values.update(
            {
                "completed_at": (
                    BASE_TIME + timedelta(seconds=2)
                ),
                "completed_by": "worker-001",
            }
        )

    return ApplicationJobCancellationRequestRecord.model_validate(
        values
    )


def service(
    *,
    jobs: list[ApplicationJobRecord] | None = None,
    cancellations: list[
        ApplicationJobCancellationRequestRecord
    ]
    | None = None,
) -> tuple[
    ApplicationCancellationService,
    InMemoryApplicationJobRepository,
    InMemoryApplicationCancellationRepository,
]:
    """Return deterministic cancellation persistence."""

    job_repository = InMemoryApplicationJobRepository(
        jobs or []
    )
    cancellation_repository = (
        InMemoryApplicationCancellationRepository(
            cancellations or []
        )
    )

    value = ApplicationCancellationService(
        job_repository=job_repository,
        cancellation_repository=cancellation_repository,
        cancellation_id_factory=lambda: "cancellation-001",
    )

    return (
        value,
        job_repository,
        cancellation_repository,
    )


def test_request_cancellation_persists_both_records() -> None:
    value, job_repository, cancellation_repository = (
        service(jobs=[job()])
    )

    result = value.request(
        job_id="job-001",
        requested_by="user-001",
        reason="Stop this research task.",
        now=BASE_TIME,
    )

    assert result.status is (
        ApplicationCancellationStatus.REQUESTED
    )
    assert result.cancellation_request_id == (
        "cancellation-001"
    )

    stored_job = job_repository.require("job-001")

    assert stored_job.status is (
        ApplicationJobStatus.CANCELLATION_REQUESTED
    )
    assert stored_job.cancellation is not None
    assert stored_job.cancellation.cancellation_id == (
        "cancellation-001"
    )
    assert cancellation_repository.require(
        "cancellation-001"
    ) == result


def test_terminal_job_cannot_be_cancelled() -> None:
    value, _, _ = service(
        jobs=[
            job(
                status=ApplicationJobStatus.SUCCEEDED
            )
        ]
    )

    with pytest.raises(
        ApplicationJobCannotBeCancelledError,
        match=(
            "terminal application job cannot be cancelled"
        ),
    ):
        value.request(
            job_id="job-001",
            requested_by="user-001",
            reason="Too late.",
            now=BASE_TIME + timedelta(seconds=2),
        )


def test_duplicate_active_request_is_rejected() -> None:
    existing = cancellation_record()
    value, _, _ = service(
        jobs=[job()],
        cancellations=[existing],
    )

    with pytest.raises(
        ApplicationCancellationAlreadyActiveError,
        match=(
            "application job already has an active "
            "cancellation request"
        ),
    ):
        value.request(
            job_id="job-001",
            requested_by="user-002",
            reason="Duplicate cancellation.",
            now=BASE_TIME + timedelta(seconds=1),
        )


def test_acknowledge_request() -> None:
    value, _, repository = service(
        jobs=[job()],
        cancellations=[cancellation_record()],
    )

    acknowledged = value.acknowledge(
        cancellation_request_id="cancellation-001",
        acknowledged_by="worker-001",
        now=BASE_TIME + timedelta(seconds=1),
    )

    assert acknowledged.status is (
        ApplicationCancellationStatus.ACKNOWLEDGED
    )
    assert acknowledged.acknowledged_by == "worker-001"
    assert acknowledged.record_version == 2
    assert repository.require(
        "cancellation-001"
    ) == acknowledged


def test_complete_cancellation_updates_job() -> None:
    value, job_repository, _ = service(
        jobs=[job()]
    )

    requested = value.request(
        job_id="job-001",
        requested_by="user-001",
        reason="Stop this task.",
        now=BASE_TIME,
    )

    acknowledged = value.acknowledge(
        cancellation_request_id=(
            requested.cancellation_request_id
        ),
        acknowledged_by="worker-001",
        now=BASE_TIME + timedelta(seconds=1),
    )

    completed = value.complete(
        cancellation_request_id=(
            acknowledged.cancellation_request_id
        ),
        completed_by="worker-001",
        now=BASE_TIME + timedelta(seconds=2),
    )

    assert completed.status is (
        ApplicationCancellationStatus.COMPLETED
    )
    assert completed.completed_by == "worker-001"
    assert completed.record_version == 3

    stored_job = job_repository.require("job-001")

    assert stored_job.status is (
        ApplicationJobStatus.CANCELLED
    )
    assert stored_job.finished_at == (
        BASE_TIME + timedelta(seconds=2)
    )
    assert stored_job.terminal is True


def test_request_can_complete_without_acknowledgement() -> None:
    value, job_repository, _ = service(
        jobs=[job()]
    )

    requested = value.request(
        job_id="job-001",
        requested_by="user-001",
        reason="Immediate cancellation.",
        now=BASE_TIME,
        force=True,
    )

    completed = value.complete(
        cancellation_request_id=(
            requested.cancellation_request_id
        ),
        completed_by="system",
        now=BASE_TIME + timedelta(seconds=1),
    )

    assert completed.status is (
        ApplicationCancellationStatus.COMPLETED
    )
    assert job_repository.require(
        "job-001"
    ).status is ApplicationJobStatus.CANCELLED


def test_completed_request_cannot_be_completed_again() -> None:
    completed_record = cancellation_record(
        status=ApplicationCancellationStatus.COMPLETED
    )

    value, _, _ = service(
        jobs=[job()],
        cancellations=[completed_record],
    )

    with pytest.raises(
        ApplicationCancellationStateError,
        match=(
            "completed cancellation cannot be completed again"
        ),
    ):
        value.complete(
            cancellation_request_id="cancellation-001",
            completed_by="worker-001",
            now=BASE_TIME + timedelta(seconds=3),
        )


def test_repository_lookup_is_case_insensitive() -> None:
    repository = (
        InMemoryApplicationCancellationRepository()
    )
    stored = cancellation_record(
        cancellation_request_id="Cancellation-001"
    )

    repository.create(stored)

    assert repository.get("cancellation-001") == stored


def test_repository_rejects_duplicate_id() -> None:
    repository = (
        InMemoryApplicationCancellationRepository(
            [
                cancellation_record(
                    cancellation_request_id=(
                        "Cancellation-001"
                    )
                )
            ]
        )
    )

    with pytest.raises(
        ApplicationCancellationAlreadyExistsError,
        match=(
            "application cancellation request already exists"
        ),
    ):
        repository.create(
            cancellation_record(
                cancellation_request_id=(
                    "cancellation-001"
                )
            )
        )


def test_repository_rejects_stale_version() -> None:
    stored = cancellation_record(record_version=2)
    repository = (
        InMemoryApplicationCancellationRepository(
            [stored]
        )
    )

    updated = stored.model_copy(
        update={"record_version": 3}
    )

    with pytest.raises(
        ApplicationCancellationVersionConflictError,
        match=(
            "application cancellation version conflict: "
            "expected 1, stored 2"
        ),
    ):
        repository.update(
            updated,
            expected_version=1,
        )


def test_acknowledged_record_requires_details() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "acknowledged cancellation requires "
            "acknowledgement details"
        ),
    ):
        ApplicationJobCancellationRequestRecord(
            cancellation_request_id="cancellation-invalid",
            job_id="job-001",
            request_id="research-001",
            workspace_id="workspace-001",
            requested_by="user-001",
            reason="Cancel.",
            status=(
                ApplicationCancellationStatus.ACKNOWLEDGED
            ),
            requested_at=BASE_TIME,
        )


def test_naive_now_is_rejected() -> None:
    value, _, _ = service(jobs=[job()])

    with pytest.raises(
        ApplicationCancellationServiceError,
        match="now must be timezone-aware",
    ):
        value.request(
            job_id="job-001",
            requested_by="user-001",
            reason="Cancel.",
            now=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                4,
                20,
            ),
        )
