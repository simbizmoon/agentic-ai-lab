"""In-memory implementation of the execution repository."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.application.execution_record import (
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
)
from app.application.execution_repository import (
    ApplicationExecutionRepository,
)
from app.application.execution_repository_error import (
    ApplicationExecutionAlreadyExistsError,
    ApplicationExecutionNotFoundError,
    ApplicationExecutionVersionConflictError,
)
from app.application.execution_repository_query import (
    ApplicationExecutionPage,
    ApplicationExecutionQuery,
    ApplicationExecutionSortDirection,
    ApplicationExecutionSortField,
)


class InMemoryApplicationExecutionRepository(
    ApplicationExecutionRepository
):
    """Store application execution records in process memory."""

    def __init__(
        self,
        records: list[ApplicationExecutionRecord] | None = None,
    ) -> None:
        self._records: dict[str, ApplicationExecutionRecord] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        """Persist a new execution record."""

        key = self._normalize_id(record.execution_id)

        with self._lock:
            if key in self._records:
                raise ApplicationExecutionAlreadyExistsError(
                    "application execution already exists: "
                    f"{record.execution_id}"
                )

            self._records[key] = record

        return record

    def get(
        self,
        execution_id: str,
    ) -> ApplicationExecutionRecord | None:
        """Return one execution record or None."""

        key = self._normalize_id(execution_id)

        with self._lock:
            return self._records.get(key)

    def update(
        self,
        record: ApplicationExecutionRecord,
        *,
        expected_version: int,
    ) -> ApplicationExecutionRecord:
        """Replace a record using optimistic concurrency."""

        if expected_version < 1:
            raise ApplicationExecutionVersionConflictError(
                "expected_version must be at least 1"
            )

        key = self._normalize_id(record.execution_id)

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationExecutionNotFoundError(
                    "application execution was not found: "
                    f"{record.execution_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationExecutionVersionConflictError(
                    "application execution version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            required_new_version = expected_version + 1

            if record.record_version != required_new_version:
                raise ApplicationExecutionVersionConflictError(
                    "updated execution record_version must equal "
                    f"{required_new_version}"
                )

            self._records[key] = record

        return record

    def list(
        self,
        query: ApplicationExecutionQuery,
    ) -> ApplicationExecutionPage:
        """Return filtered, sorted, paginated records."""

        with self._lock:
            records = list(self._records.values())

        filtered = self._filter_records(
            records=records,
            query=query,
        )
        ordered = self._sort_records(
            records=filtered,
            query=query,
        )

        start = query.offset
        end = start + query.page_size

        return ApplicationExecutionPage(
            items=ordered[start:end],
            total_items=len(ordered),
            page=query.page,
            page_size=query.page_size,
        )

    def count(
        self,
        query: ApplicationExecutionQuery,
    ) -> int:
        """Return the number of matching records."""

        with self._lock:
            records = list(self._records.values())

        return len(
            self._filter_records(
                records=records,
                query=query,
            )
        )

    def clear(self) -> None:
        """Remove all records from the repository."""

        with self._lock:
            self._records.clear()

    @classmethod
    def _filter_records(
        cls,
        *,
        records: list[ApplicationExecutionRecord],
        query: ApplicationExecutionQuery,
    ) -> list[ApplicationExecutionRecord]:
        """Apply every repository query filter."""

        execution_ids = {
            cls._normalize_id(value)
            for value in query.execution_ids
        }

        terminal_statuses = {
            ApplicationExecutionStatus.SUCCEEDED,
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.TIMED_OUT,
        }

        filtered: list[ApplicationExecutionRecord] = []

        for record in records:
            if (
                execution_ids
                and cls._normalize_id(record.execution_id)
                not in execution_ids
            ):
                continue

            if (
                query.root_execution_id is not None
                and not cls._same_id(
                    record.root_execution_id,
                    query.root_execution_id,
                )
            ):
                continue

            if (
                query.parent_execution_id is not None
                and (
                    record.parent_execution_id is None
                    or not cls._same_id(
                        record.parent_execution_id,
                        query.parent_execution_id,
                    )
                )
            ):
                continue

            if (
                query.request_id is not None
                and not cls._same_id(
                    record.request_id,
                    query.request_id,
                )
            ):
                continue

            if (
                query.workspace_id is not None
                and not cls._same_id(
                    record.workspace_id,
                    query.workspace_id,
                )
            ):
                continue

            if (
                query.subject_type is not None
                and record.subject_type is not query.subject_type
            ):
                continue

            if (
                query.subject_id is not None
                and not cls._same_id(
                    record.subject_id,
                    query.subject_id,
                )
            ):
                continue

            if (
                query.statuses
                and record.status not in query.statuses
            ):
                continue

            if (
                query.minimum_attempt_number is not None
                and record.attempt_number
                < query.minimum_attempt_number
            ):
                continue

            if (
                query.maximum_attempt_number is not None
                and record.attempt_number
                > query.maximum_attempt_number
            ):
                continue

            if (
                query.created_from is not None
                and record.created_at < query.created_from
            ):
                continue

            if (
                query.created_to is not None
                and record.created_at > query.created_to
            ):
                continue

            if (
                query.terminal_only is True
                and record.status not in terminal_statuses
            ):
                continue

            if (
                query.terminal_only is False
                and record.status in terminal_statuses
            ):
                continue

            filtered.append(record)

        return filtered

    @classmethod
    def _sort_records(
        cls,
        *,
        records: list[ApplicationExecutionRecord],
        query: ApplicationExecutionQuery,
    ) -> list[ApplicationExecutionRecord]:
        """Sort records deterministically."""

        reverse = (
            query.sort_direction
            is ApplicationExecutionSortDirection.DESCENDING
        )

        return sorted(
            records,
            key=lambda record: (
                cls._sort_value(
                    record=record,
                    field=query.sort_field,
                ),
                cls._normalize_id(record.execution_id),
            ),
            reverse=reverse,
        )

    @staticmethod
    def _sort_value(
        *,
        record: ApplicationExecutionRecord,
        field: ApplicationExecutionSortField,
    ) -> Any:
        """Return a comparable value for one sort field."""

        if field is ApplicationExecutionSortField.CREATED_AT:
            return record.created_at

        if field is ApplicationExecutionSortField.QUEUED_AT:
            return record.queued_at or datetime.min.replace(
                tzinfo=UTC
            )

        if field is ApplicationExecutionSortField.STARTED_AT:
            return record.started_at or datetime.min.replace(
                tzinfo=UTC
            )

        if field is ApplicationExecutionSortField.FINISHED_AT:
            return record.finished_at or datetime.min.replace(
                tzinfo=UTC
            )

        if field is ApplicationExecutionSortField.ATTEMPT_NUMBER:
            return record.attempt_number

        return record.record_version

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize an identifier for repository lookup."""

        return value.strip().casefold()

    @classmethod
    def _same_id(
        cls,
        left: str,
        right: str,
    ) -> bool:
        """Return whether two identifiers are equivalent."""

        return cls._normalize_id(left) == cls._normalize_id(
            right
        )
