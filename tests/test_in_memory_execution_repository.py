"""Tests for the in-memory execution repository."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.execution_record import (
    ApplicationExecutionFailure,
    ApplicationExecutionFailureCategory,
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.execution_repository_error import (
    ApplicationExecutionAlreadyExistsError,
    ApplicationExecutionNotFoundError,
    ApplicationExecutionVersionConflictError,
)
from app.application.execution_repository_query import (
    ApplicationExecutionQuery,
    ApplicationExecutionSortDirection,
    ApplicationExecutionSortField,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    30,
    tzinfo=UTC,
)


def failure() -> ApplicationExecutionFailure:
    """Return one retryable failure."""

    return ApplicationExecutionFailure(
        category=ApplicationExecutionFailureCategory.TIMEOUT,
        code="TIMEOUT",
        message="The execution timed out.",
        retryable=True,
        retry_reason="The timeout may be temporary.",
    )


def record(
    *,
    execution_id: str,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    subject_id: str = "agent-search-001",
    status: ApplicationExecutionStatus = (
        ApplicationExecutionStatus.PENDING
    ),
    attempt_number: int = 1,
    maximum_attempts: int = 3,
    previous_attempt_execution_id: str | None = None,
    created_offset: int = 0,
    record_version: int = 1,
) -> ApplicationExecutionRecord:
    """Return one execution record."""

    values: dict[str, object] = {
        "execution_id": execution_id,
        "root_execution_id": "execution-root",
        "request_id": request_id,
        "workspace_id": workspace_id,
        "subject_type": (
            ApplicationExecutionSubjectType.AGENT
        ),
        "subject_id": subject_id,
        "status": status,
        "attempt_number": attempt_number,
        "maximum_attempts": maximum_attempts,
        "previous_attempt_execution_id": (
            previous_attempt_execution_id
        ),
        "created_at": (
            BASE_TIME + timedelta(seconds=created_offset)
        ),
        "record_version": record_version,
    }

    if status is ApplicationExecutionStatus.RUNNING:
        values["started_at"] = values["created_at"]

    if status in {
        ApplicationExecutionStatus.SUCCEEDED,
        ApplicationExecutionStatus.FAILED,
        ApplicationExecutionStatus.TIMED_OUT,
    }:
        values["started_at"] = values["created_at"]
        values["finished_at"] = (
            values["created_at"] + timedelta(seconds=1)
        )

    if status in {
        ApplicationExecutionStatus.FAILED,
        ApplicationExecutionStatus.TIMED_OUT,
    }:
        values["failure"] = failure()

    return ApplicationExecutionRecord.model_validate(values)


def repository_with_records(
) -> InMemoryApplicationExecutionRepository:
    """Return a populated repository."""

    return InMemoryApplicationExecutionRepository(
        [
            record(
                execution_id="execution-001",
                status=ApplicationExecutionStatus.PENDING,
                created_offset=1,
            ),
            record(
                execution_id="execution-002",
                status=ApplicationExecutionStatus.RUNNING,
                created_offset=2,
            ),
            record(
                execution_id="execution-003",
                status=ApplicationExecutionStatus.SUCCEEDED,
                created_offset=3,
            ),
            record(
                execution_id="execution-004",
                request_id="research-002",
                workspace_id="workspace-002",
                subject_id="agent-reader-001",
                status=ApplicationExecutionStatus.FAILED,
                created_offset=4,
            ),
        ]
    )


def test_create_and_get_record() -> None:
    repository = InMemoryApplicationExecutionRepository()
    stored = record(execution_id="execution-001")

    assert repository.create(stored) == stored
    assert repository.get("execution-001") == stored


def test_lookup_is_case_insensitive() -> None:
    repository = InMemoryApplicationExecutionRepository()
    stored = record(execution_id="Execution-001")

    repository.create(stored)

    assert repository.get("execution-001") == stored
    assert repository.exists("EXECUTION-001") is True


def test_duplicate_execution_is_rejected() -> None:
    repository = InMemoryApplicationExecutionRepository()
    repository.create(
        record(execution_id="Execution-001")
    )

    with pytest.raises(
        ApplicationExecutionAlreadyExistsError,
        match=(
            "application execution already exists: "
            "execution-001"
        ),
    ):
        repository.create(
            record(execution_id="execution-001")
        )


def test_update_increments_record_version() -> None:
    repository = InMemoryApplicationExecutionRepository()
    original = record(execution_id="execution-001")
    repository.create(original)

    updated = original.model_copy(
        update={
            "status": ApplicationExecutionStatus.RUNNING,
            "started_at": BASE_TIME,
            "record_version": 2,
        }
    )

    result = repository.update(
        updated,
        expected_version=1,
    )

    assert result.record_version == 2
    assert repository.require(
        "execution-001"
    ).status is ApplicationExecutionStatus.RUNNING


def test_update_rejects_stale_expected_version() -> None:
    repository = InMemoryApplicationExecutionRepository(
        [
            record(
                execution_id="execution-001",
                record_version=2,
            )
        ]
    )

    updated = record(
        execution_id="execution-001",
        record_version=2,
    ).model_copy(
        update={"record_version": 3}
    )

    with pytest.raises(
        ApplicationExecutionVersionConflictError,
        match=(
            "application execution version conflict: "
            "expected 1, stored 2"
        ),
    ):
        repository.update(
            updated,
            expected_version=1,
        )


def test_update_requires_next_record_version() -> None:
    repository = InMemoryApplicationExecutionRepository(
        [record(execution_id="execution-001")]
    )

    unchanged_version = record(
        execution_id="execution-001",
        record_version=1,
    )

    with pytest.raises(
        ApplicationExecutionVersionConflictError,
        match=(
            "updated execution record_version must equal 2"
        ),
    ):
        repository.update(
            unchanged_version,
            expected_version=1,
        )


def test_update_missing_record_is_rejected() -> None:
    repository = InMemoryApplicationExecutionRepository()

    missing = record(
        execution_id="execution-missing",
        record_version=2,
    )

    with pytest.raises(
        ApplicationExecutionNotFoundError,
        match=(
            "application execution was not found: "
            "execution-missing"
        ),
    ):
        repository.update(
            missing,
            expected_version=1,
        )


def test_list_defaults_to_created_at_descending() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery()
    )

    assert [
        item.execution_id
        for item in page.items
    ] == [
        "execution-004",
        "execution-003",
        "execution-002",
        "execution-001",
    ]


def test_list_can_sort_created_at_ascending() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            sort_field=(
                ApplicationExecutionSortField.CREATED_AT
            ),
            sort_direction=(
                ApplicationExecutionSortDirection.ASCENDING
            ),
        )
    )

    assert [
        item.execution_id
        for item in page.items
    ] == [
        "execution-001",
        "execution-002",
        "execution-003",
        "execution-004",
    ]


def test_filter_by_execution_ids() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            execution_ids=[
                "EXECUTION-001",
                "execution-003",
            ]
        )
    )

    assert {
        item.execution_id
        for item in page.items
    } == {
        "execution-001",
        "execution-003",
    }


def test_filter_by_request_and_workspace() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            request_id="research-002",
            workspace_id="workspace-002",
        )
    )

    assert len(page.items) == 1
    assert page.items[0].execution_id == "execution-004"


def test_filter_by_subject_id() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            subject_id="agent-reader-001",
        )
    )

    assert len(page.items) == 1
    assert page.items[0].execution_id == "execution-004"


def test_filter_by_status() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            statuses=[
                ApplicationExecutionStatus.RUNNING,
                ApplicationExecutionStatus.SUCCEEDED,
            ]
        )
    )

    assert {
        item.status
        for item in page.items
    } == {
        ApplicationExecutionStatus.RUNNING,
        ApplicationExecutionStatus.SUCCEEDED,
    }


def test_filter_terminal_records() -> None:
    repository = repository_with_records()

    terminal_page = repository.list(
        ApplicationExecutionQuery(
            terminal_only=True
        )
    )
    nonterminal_page = repository.list(
        ApplicationExecutionQuery(
            terminal_only=False
        )
    )

    assert {
        item.execution_id
        for item in terminal_page.items
    } == {
        "execution-003",
        "execution-004",
    }

    assert {
        item.execution_id
        for item in nonterminal_page.items
    } == {
        "execution-001",
        "execution-002",
    }


def test_filter_by_created_range() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            created_from=BASE_TIME + timedelta(seconds=2),
            created_to=BASE_TIME + timedelta(seconds=3),
        )
    )

    assert {
        item.execution_id
        for item in page.items
    } == {
        "execution-002",
        "execution-003",
    }


def test_count_uses_same_filters_as_list() -> None:
    repository = repository_with_records()
    query = ApplicationExecutionQuery(
        terminal_only=True
    )

    assert repository.count(query) == 2
    assert repository.list(query).total_items == 2


def test_pagination_returns_requested_page() -> None:
    page = repository_with_records().list(
        ApplicationExecutionQuery(
            sort_direction=(
                ApplicationExecutionSortDirection.ASCENDING
            ),
            page=2,
            page_size=2,
        )
    )

    assert page.total_items == 4
    assert page.total_pages == 2
    assert [
        item.execution_id
        for item in page.items
    ] == [
        "execution-003",
        "execution-004",
    ]


def test_clear_removes_all_records() -> None:
    repository = repository_with_records()

    repository.clear()

    assert repository.count(
        ApplicationExecutionQuery()
    ) == 0
