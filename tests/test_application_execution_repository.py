"""Tests for the application execution repository contract."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.execution_record import (
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.execution_repository import (
    ApplicationExecutionRepository,
)
from app.application.execution_repository_error import (
    ApplicationExecutionNotFoundError,
)
from app.application.execution_repository_query import (
    ApplicationExecutionPage,
    ApplicationExecutionQuery,
    ApplicationExecutionSortDirection,
    ApplicationExecutionSortField,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    20,
    tzinfo=UTC,
)


def execution_record(
    *,
    execution_id: str = "execution-001",
) -> ApplicationExecutionRecord:
    """Return one pending execution record."""

    return ApplicationExecutionRecord(
        execution_id=execution_id,
        root_execution_id=execution_id,
        request_id="research-001",
        workspace_id="workspace-001",
        subject_type=ApplicationExecutionSubjectType.AGENT,
        subject_id="agent-search-001",
        status=ApplicationExecutionStatus.PENDING,
        created_at=BASE_TIME,
    )


class StubExecutionRepository(
    ApplicationExecutionRepository
):
    """Minimal repository used to test interface helpers."""

    def __init__(
        self,
        records: list[ApplicationExecutionRecord] | None = None,
    ) -> None:
        self._records = {
            record.execution_id: record
            for record in records or []
        }

    def create(
        self,
        record: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        self._records[record.execution_id] = record
        return record

    def get(
        self,
        execution_id: str,
    ) -> ApplicationExecutionRecord | None:
        return self._records.get(execution_id)

    def update(
        self,
        record: ApplicationExecutionRecord,
        *,
        expected_version: int,
    ) -> ApplicationExecutionRecord:
        del expected_version
        self._records[record.execution_id] = record
        return record

    def list(
        self,
        query: ApplicationExecutionQuery,
    ) -> ApplicationExecutionPage:
        records = list(self._records.values())

        return ApplicationExecutionPage(
            items=records[
                query.offset:
                query.offset + query.page_size
            ],
            total_items=len(records),
            page=query.page,
            page_size=query.page_size,
        )

    def count(
        self,
        query: ApplicationExecutionQuery,
    ) -> int:
        del query
        return len(self._records)


def test_repository_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ApplicationExecutionRepository()


def test_require_returns_existing_record() -> None:
    stored = execution_record()
    repository = StubExecutionRepository([stored])

    assert repository.require("execution-001") == stored


def test_require_raises_for_missing_record() -> None:
    repository = StubExecutionRepository()

    with pytest.raises(
        ApplicationExecutionNotFoundError,
        match=(
            "application execution was not found: "
            "execution-missing"
        ),
    ):
        repository.require("execution-missing")


def test_exists_reports_record_presence() -> None:
    repository = StubExecutionRepository(
        [execution_record()]
    )

    assert repository.exists("execution-001") is True
    assert repository.exists("execution-missing") is False


def test_query_defaults_are_stable() -> None:
    query = ApplicationExecutionQuery()

    assert query.page == 1
    assert query.page_size == 50
    assert query.offset == 0
    assert query.sort_field is (
        ApplicationExecutionSortField.CREATED_AT
    )
    assert query.sort_direction is (
        ApplicationExecutionSortDirection.DESCENDING
    )


def test_query_calculates_page_offset() -> None:
    query = ApplicationExecutionQuery(
        page=3,
        page_size=20,
    )

    assert query.offset == 40


def test_query_supports_execution_filters() -> None:
    query = ApplicationExecutionQuery(
        execution_ids=[
            "execution-001",
            "execution-002",
        ],
        request_id="research-001",
        workspace_id="workspace-001",
        subject_type=ApplicationExecutionSubjectType.AGENT,
        subject_id="agent-search-001",
        statuses=[
            ApplicationExecutionStatus.PENDING,
            ApplicationExecutionStatus.RUNNING,
        ],
        minimum_attempt_number=1,
        maximum_attempt_number=3,
        created_from=BASE_TIME,
        created_to=BASE_TIME + timedelta(hours=1),
        terminal_only=False,
    )

    assert len(query.execution_ids) == 2
    assert len(query.statuses) == 2


def test_query_rejects_duplicate_execution_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "execution_ids must not contain duplicates"
        ),
    ):
        ApplicationExecutionQuery(
            execution_ids=[
                "EXECUTION-001",
                "execution-001",
            ]
        )


def test_query_rejects_duplicate_statuses() -> None:
    with pytest.raises(
        ValidationError,
        match="statuses must not contain duplicates",
    ):
        ApplicationExecutionQuery(
            statuses=[
                ApplicationExecutionStatus.PENDING,
                ApplicationExecutionStatus.PENDING,
            ]
        )


def test_query_rejects_invalid_attempt_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "minimum_attempt_number must not exceed "
            "maximum_attempt_number"
        ),
    ):
        ApplicationExecutionQuery(
            minimum_attempt_number=3,
            maximum_attempt_number=2,
        )


def test_query_rejects_invalid_date_range() -> None:
    with pytest.raises(
        ValidationError,
        match="created_from must not exceed created_to",
    ):
        ApplicationExecutionQuery(
            created_from=BASE_TIME + timedelta(hours=1),
            created_to=BASE_TIME,
        )


def test_query_rejects_naive_date() -> None:
    with pytest.raises(
        ValidationError,
        match="created_from must be timezone-aware",
    ):
        ApplicationExecutionQuery(
            created_from=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                3,
                20,
            )
        )


def test_query_rejects_oversized_page() -> None:
    with pytest.raises(ValidationError):
        ApplicationExecutionQuery(
            page_size=201,
        )


def test_page_reports_navigation() -> None:
    page = ApplicationExecutionPage(
        items=[
            execution_record(
                execution_id="execution-003"
            )
        ],
        total_items=5,
        page=2,
        page_size=2,
    )

    assert page.total_pages == 3
    assert page.has_previous_page is True
    assert page.has_next_page is True


def test_empty_page_has_zero_total_pages() -> None:
    page = ApplicationExecutionPage(
        items=[],
        total_items=0,
        page=1,
        page_size=50,
    )

    assert page.total_pages == 0
    assert page.has_previous_page is False
    assert page.has_next_page is False


def test_page_rejects_too_many_items() -> None:
    with pytest.raises(
        ValidationError,
        match="page items must not exceed page_size",
    ):
        ApplicationExecutionPage(
            items=[
                execution_record(
                    execution_id="execution-001"
                ),
                execution_record(
                    execution_id="execution-002"
                ),
            ],
            total_items=2,
            page=1,
            page_size=1,
        )


def test_page_rejects_items_over_total_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "page items must not exceed total_items"
        ),
    ):
        ApplicationExecutionPage(
            items=[execution_record()],
            total_items=0,
            page=1,
            page_size=50,
        )
