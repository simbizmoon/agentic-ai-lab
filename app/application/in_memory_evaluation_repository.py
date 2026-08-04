"""In-memory implementation of the evaluation repository."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from app.application.evaluation_record import (
    ApplicationEvaluationRecord,
)
from app.application.evaluation_repository import (
    ApplicationEvaluationRepository,
)
from app.application.evaluation_repository_error import (
    ApplicationEvaluationAlreadyExistsError,
    ApplicationEvaluationNotFoundError,
    ApplicationEvaluationVersionConflictError,
)
from app.application.evaluation_repository_query import (
    ApplicationEvaluationPage,
    ApplicationEvaluationQuery,
    ApplicationEvaluationSortDirection,
    ApplicationEvaluationSortField,
)


class InMemoryApplicationEvaluationRepository(
    ApplicationEvaluationRepository
):
    """Store application evaluation results in memory."""

    def __init__(
        self,
        records: list[ApplicationEvaluationRecord] | None = None,
    ) -> None:
        self._records: dict[
            str,
            ApplicationEvaluationRecord,
        ] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationEvaluationRecord,
    ) -> ApplicationEvaluationRecord:
        """Persist a new evaluation record."""

        key = self._normalize_id(record.evaluation_id)

        with self._lock:
            if key in self._records:
                raise ApplicationEvaluationAlreadyExistsError(
                    "application evaluation already exists: "
                    f"{record.evaluation_id}"
                )

            self._records[key] = record

        return record

    def get(
        self,
        evaluation_id: str,
    ) -> ApplicationEvaluationRecord | None:
        """Return one evaluation record or None."""

        key = self._normalize_id(evaluation_id)

        with self._lock:
            return self._records.get(key)

    def update(
        self,
        record: ApplicationEvaluationRecord,
        *,
        expected_version: int,
    ) -> ApplicationEvaluationRecord:
        """Replace a record using optimistic concurrency."""

        if expected_version < 1:
            raise ApplicationEvaluationVersionConflictError(
                "expected_version must be at least 1"
            )

        key = self._normalize_id(record.evaluation_id)

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationEvaluationNotFoundError(
                    "application evaluation was not found: "
                    f"{record.evaluation_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationEvaluationVersionConflictError(
                    "application evaluation version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            required_version = expected_version + 1

            if record.record_version != required_version:
                raise ApplicationEvaluationVersionConflictError(
                    "updated evaluation record_version must "
                    f"equal {required_version}"
                )

            self._records[key] = record

        return record

    def list(
        self,
        query: ApplicationEvaluationQuery,
    ) -> ApplicationEvaluationPage:
        """Return filtered, sorted, paginated evaluations."""

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

        return ApplicationEvaluationPage(
            items=ordered[start:end],
            total_items=len(ordered),
            page=query.page,
            page_size=query.page_size,
        )

    def count(
        self,
        query: ApplicationEvaluationQuery,
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
        """Remove every stored evaluation."""

        with self._lock:
            self._records.clear()

    @classmethod
    def _filter_records(
        cls,
        *,
        records: list[ApplicationEvaluationRecord],
        query: ApplicationEvaluationQuery,
    ) -> list[ApplicationEvaluationRecord]:
        """Apply evaluation repository filters."""

        evaluation_ids = {
            cls._normalize_id(value)
            for value in query.evaluation_ids
        }

        filtered: list[ApplicationEvaluationRecord] = []

        for record in records:
            if (
                evaluation_ids
                and cls._normalize_id(record.evaluation_id)
                not in evaluation_ids
            ):
                continue

            if (
                query.evaluation_types
                and record.evaluation_type
                not in query.evaluation_types
            ):
                continue

            if (
                query.statuses
                and record.status not in query.statuses
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

            if not cls._matches_optional_id(
                actual=record.execution_id,
                expected=query.execution_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.dataset_id,
                expected=query.dataset_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.case_id,
                expected=query.case_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.baseline_evaluation_id,
                expected=query.baseline_evaluation_id,
            ):
                continue

            if (
                query.minimum_score is not None
                and (
                    record.overall_score is None
                    or record.overall_score
                    < query.minimum_score
                )
            ):
                continue

            if (
                query.maximum_score is not None
                and (
                    record.overall_score is None
                    or record.overall_score
                    > query.maximum_score
                )
            ):
                continue

            if (
                query.blocking_only is True
                and not record.blocking_violations
            ):
                continue

            if (
                query.blocking_only is False
                and record.blocking_violations
            ):
                continue

            if (
                query.started_from is not None
                and record.started_at < query.started_from
            ):
                continue

            if (
                query.started_to is not None
                and record.started_at > query.started_to
            ):
                continue

            filtered.append(record)

        return filtered

    @classmethod
    def _sort_records(
        cls,
        *,
        records: list[ApplicationEvaluationRecord],
        query: ApplicationEvaluationQuery,
    ) -> list[ApplicationEvaluationRecord]:
        """Sort evaluation records deterministically."""

        reverse = (
            query.sort_direction
            is ApplicationEvaluationSortDirection.DESCENDING
        )

        return sorted(
            records,
            key=lambda record: (
                cls._sort_value(
                    record=record,
                    field=query.sort_field,
                ),
                cls._normalize_id(record.evaluation_id),
            ),
            reverse=reverse,
        )

    @staticmethod
    def _sort_value(
        *,
        record: ApplicationEvaluationRecord,
        field: ApplicationEvaluationSortField,
    ) -> Any:
        """Return a comparable sort value."""

        if field is ApplicationEvaluationSortField.STARTED_AT:
            return record.started_at

        if field is ApplicationEvaluationSortField.FINISHED_AT:
            return record.finished_at

        if field is ApplicationEvaluationSortField.OVERALL_SCORE:
            return (
                record.overall_score
                if record.overall_score is not None
                else -1.0
            )

        return record.record_version

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize one identifier."""

        return value.strip().casefold()

    @classmethod
    def _same_id(
        cls,
        left: str,
        right: str,
    ) -> bool:
        """Return whether identifiers are equivalent."""

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
        """Match one optional query identifier."""

        if expected is None:
            return True

        if actual is None:
            return False

        return cls._same_id(actual, expected)
