"""In-memory implementation of the background-job repository."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any

from app.application.job_record import (
    ApplicationJobRecord,
    ApplicationJobStatus,
)
from app.application.job_repository import (
    ApplicationJobRepository,
)
from app.application.job_repository_error import (
    ApplicationJobAlreadyExistsError,
    ApplicationJobNotFoundError,
    ApplicationJobVersionConflictError,
)
from app.application.job_repository_query import (
    ApplicationJobPage,
    ApplicationJobQuery,
    ApplicationJobSortDirection,
    ApplicationJobSortField,
)


class InMemoryApplicationJobRepository(
    ApplicationJobRepository
):
    """Store background jobs in process memory."""

    def __init__(
        self,
        records: list[ApplicationJobRecord] | None = None,
    ) -> None:
        self._records: dict[str, ApplicationJobRecord] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationJobRecord,
    ) -> ApplicationJobRecord:
        """Persist a new background job."""

        key = self._normalize_id(record.job_id)

        with self._lock:
            if key in self._records:
                raise ApplicationJobAlreadyExistsError(
                    "application job already exists: "
                    f"{record.job_id}"
                )

            self._records[key] = record

        return record

    def get(
        self,
        job_id: str,
    ) -> ApplicationJobRecord | None:
        """Return one background job or None."""

        key = self._normalize_id(job_id)

        with self._lock:
            return self._records.get(key)

    def update(
        self,
        record: ApplicationJobRecord,
        *,
        expected_version: int,
    ) -> ApplicationJobRecord:
        """Replace a job using optimistic concurrency."""

        if expected_version < 1:
            raise ApplicationJobVersionConflictError(
                "expected_version must be at least 1"
            )

        key = self._normalize_id(record.job_id)

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationJobNotFoundError(
                    "application job was not found: "
                    f"{record.job_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationJobVersionConflictError(
                    "application job version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            required_version = expected_version + 1

            if record.record_version != required_version:
                raise ApplicationJobVersionConflictError(
                    "updated job record_version must equal "
                    f"{required_version}"
                )

            self._records[key] = record

        return record

    def list(
        self,
        query: ApplicationJobQuery,
    ) -> ApplicationJobPage:
        """Return filtered, sorted, paginated jobs."""

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

        return ApplicationJobPage(
            items=ordered[start:end],
            total_items=len(ordered),
            page=query.page,
            page_size=query.page_size,
        )

    def count(
        self,
        query: ApplicationJobQuery,
    ) -> int:
        """Return the number of matching jobs."""

        with self._lock:
            records = list(self._records.values())

        return len(
            self._filter_records(
                records=records,
                query=query,
            )
        )

    def find_available(
        self,
        *,
        queue_name: str,
        now: datetime,
        limit: int = 1,
    ) -> list[ApplicationJobRecord]:
        """Return executable jobs in worker pickup order."""

        if not queue_name.strip():
            raise ValueError(
                "queue_name must not be blank"
            )

        if now.tzinfo is None:
            raise ValueError(
                "now must be timezone-aware"
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        executable_statuses = {
            ApplicationJobStatus.PENDING,
            ApplicationJobStatus.SCHEDULED,
            ApplicationJobStatus.QUEUED,
            ApplicationJobStatus.RETRY_SCHEDULED,
        }

        with self._lock:
            candidates = [
                record
                for record in self._records.values()
                if (
                    self._same_id(
                        record.queue_name,
                        queue_name,
                    )
                    and record.status in executable_statuses
                    and record.available_at <= now
                )
            ]

        ordered = sorted(
            candidates,
            key=lambda record: (
                -int(record.priority),
                record.available_at,
                record.created_at,
                self._normalize_id(record.job_id),
            ),
        )

        return ordered[:limit]

    def snapshot_state(self) -> dict[str, object]:
        """Return an isolated repository state snapshot."""

        with self._lock:
            return deepcopy(self._records)

    def restore_state(
        self,
        snapshot: dict[str, object],
    ) -> None:
        """Restore a previously captured repository state."""

        with self._lock:
            self._records = deepcopy(snapshot)

    def clear(self) -> None:
        """Remove all stored jobs."""

        with self._lock:
            self._records.clear()

    @classmethod
    def _filter_records(
        cls,
        *,
        records: list[ApplicationJobRecord],
        query: ApplicationJobQuery,
    ) -> list[ApplicationJobRecord]:
        """Apply every background-job query filter."""

        job_ids = {
            cls._normalize_id(value)
            for value in query.job_ids
        }
        queue_names = {
            cls._normalize_id(value)
            for value in query.queue_names
        }

        terminal_statuses = {
            ApplicationJobStatus.SUCCEEDED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.CANCELLED,
            ApplicationJobStatus.DEAD_LETTERED,
        }

        filtered: list[ApplicationJobRecord] = []

        for record in records:
            if (
                job_ids
                and cls._normalize_id(record.job_id)
                not in job_ids
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.root_job_id,
                expected=query.root_job_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.parent_job_id,
                expected=query.parent_job_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.previous_attempt_job_id,
                expected=query.previous_attempt_job_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.request_id,
                expected=query.request_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.workspace_id,
                expected=query.workspace_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.execution_id,
                expected=query.execution_id,
            ):
                continue

            if (
                query.job_types
                and record.job_type not in query.job_types
            ):
                continue

            if (
                queue_names
                and cls._normalize_id(record.queue_name)
                not in queue_names
            ):
                continue

            if (
                query.priorities
                and record.priority not in query.priorities
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
                query.available_from is not None
                and record.available_at < query.available_from
            ):
                continue

            if (
                query.available_to is not None
                and record.available_at > query.available_to
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

            if (
                query.leased_only is True
                and record.lease is None
            ):
                continue

            if (
                query.leased_only is False
                and record.lease is not None
            ):
                continue

            filtered.append(record)

        return filtered

    @classmethod
    def _sort_records(
        cls,
        *,
        records: list[ApplicationJobRecord],
        query: ApplicationJobQuery,
    ) -> list[ApplicationJobRecord]:
        """Sort jobs deterministically."""

        reverse = (
            query.sort_direction
            is ApplicationJobSortDirection.DESCENDING
        )

        return sorted(
            records,
            key=lambda record: (
                cls._sort_value(
                    record=record,
                    field=query.sort_field,
                ),
                cls._normalize_id(record.job_id),
            ),
            reverse=reverse,
        )

    @staticmethod
    def _sort_value(
        *,
        record: ApplicationJobRecord,
        field: ApplicationJobSortField,
    ) -> Any:
        """Return one comparable job sort value."""

        if field is ApplicationJobSortField.CREATED_AT:
            return record.created_at

        if field is ApplicationJobSortField.AVAILABLE_AT:
            return record.available_at

        if field is ApplicationJobSortField.PRIORITY:
            return int(record.priority)

        if field is ApplicationJobSortField.ATTEMPT_NUMBER:
            return record.attempt_number

        return record.record_version

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize one repository identifier."""

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

    @classmethod
    def _matches_optional_id(
        cls,
        *,
        actual: str | None,
        expected: str | None,
    ) -> bool:
        """Match one optional identifier filter."""

        if expected is None:
            return True

        if actual is None:
            return False

        return cls._same_id(actual, expected)
