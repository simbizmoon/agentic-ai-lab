"""In-memory implementation of the guardrail repository."""

from __future__ import annotations

from threading import RLock
from typing import Any

from app.application.guardrail_record import (
    ApplicationGuardrailRecord,
)
from app.application.guardrail_repository import (
    ApplicationGuardrailRepository,
)
from app.application.guardrail_repository_error import (
    ApplicationGuardrailAlreadyExistsError,
    ApplicationGuardrailNotFoundError,
    ApplicationGuardrailVersionConflictError,
)
from app.application.guardrail_repository_query import (
    ApplicationGuardrailPage,
    ApplicationGuardrailQuery,
    ApplicationGuardrailSortDirection,
    ApplicationGuardrailSortField,
)


class InMemoryApplicationGuardrailRepository(
    ApplicationGuardrailRepository
):
    """Store guardrail results in process memory."""

    def __init__(
        self,
        records: list[ApplicationGuardrailRecord] | None = None,
    ) -> None:
        self._records: dict[
            str,
            ApplicationGuardrailRecord,
        ] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationGuardrailRecord,
    ) -> ApplicationGuardrailRecord:
        """Persist a new guardrail evaluation."""

        key = self._normalize_id(
            record.guardrail_evaluation_id
        )

        with self._lock:
            if key in self._records:
                raise ApplicationGuardrailAlreadyExistsError(
                    "application guardrail evaluation already "
                    f"exists: {record.guardrail_evaluation_id}"
                )

            self._records[key] = record

        return record

    def get(
        self,
        guardrail_evaluation_id: str,
    ) -> ApplicationGuardrailRecord | None:
        """Return one guardrail record or None."""

        key = self._normalize_id(
            guardrail_evaluation_id
        )

        with self._lock:
            return self._records.get(key)

    def update(
        self,
        record: ApplicationGuardrailRecord,
        *,
        expected_version: int,
    ) -> ApplicationGuardrailRecord:
        """Replace a record using optimistic concurrency."""

        if expected_version < 1:
            raise ApplicationGuardrailVersionConflictError(
                "expected_version must be at least 1"
            )

        key = self._normalize_id(
            record.guardrail_evaluation_id
        )

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationGuardrailNotFoundError(
                    "application guardrail evaluation was not "
                    f"found: {record.guardrail_evaluation_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationGuardrailVersionConflictError(
                    "application guardrail version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            required_version = expected_version + 1

            if record.record_version != required_version:
                raise ApplicationGuardrailVersionConflictError(
                    "updated guardrail record_version must "
                    f"equal {required_version}"
                )

            self._records[key] = record

        return record

    def list(
        self,
        query: ApplicationGuardrailQuery,
    ) -> ApplicationGuardrailPage:
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

        return ApplicationGuardrailPage(
            items=ordered[start:end],
            total_items=len(ordered),
            page=query.page,
            page_size=query.page_size,
        )

    def count(
        self,
        query: ApplicationGuardrailQuery,
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
        """Remove all stored guardrail records."""

        with self._lock:
            self._records.clear()

    @classmethod
    def _filter_records(
        cls,
        *,
        records: list[ApplicationGuardrailRecord],
        query: ApplicationGuardrailQuery,
    ) -> list[ApplicationGuardrailRecord]:
        """Apply every guardrail query filter."""

        evaluation_ids = {
            cls._normalize_id(value)
            for value in query.guardrail_evaluation_ids
        }

        filtered: list[ApplicationGuardrailRecord] = []

        for record in records:
            if (
                evaluation_ids
                and cls._normalize_id(
                    record.guardrail_evaluation_id
                )
                not in evaluation_ids
            ):
                continue

            if (
                query.scopes
                and record.scope not in query.scopes
            ):
                continue

            if (
                query.decisions
                and record.decision not in query.decisions
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

            if not cls._matches_optional_id(
                actual=record.assignment_id,
                expected=query.assignment_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.agent_id,
                expected=query.agent_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.target_id,
                expected=query.target_id,
            ):
                continue

            if not cls._matches_optional_id(
                actual=record.target_type,
                expected=query.target_type,
            ):
                continue

            if (
                query.blocking_only is True
                and record.blocking_violation_count == 0
            ):
                continue

            if (
                query.blocking_only is False
                and record.blocking_violation_count > 0
            ):
                continue

            if (
                query.evaluated_from is not None
                and record.evaluated_at
                < query.evaluated_from
            ):
                continue

            if (
                query.evaluated_to is not None
                and record.evaluated_at
                > query.evaluated_to
            ):
                continue

            filtered.append(record)

        return filtered

    @classmethod
    def _sort_records(
        cls,
        *,
        records: list[ApplicationGuardrailRecord],
        query: ApplicationGuardrailQuery,
    ) -> list[ApplicationGuardrailRecord]:
        """Sort guardrail records deterministically."""

        reverse = (
            query.sort_direction
            is ApplicationGuardrailSortDirection.DESCENDING
        )

        return sorted(
            records,
            key=lambda record: (
                cls._sort_value(
                    record=record,
                    field=query.sort_field,
                ),
                cls._normalize_id(
                    record.guardrail_evaluation_id
                ),
            ),
            reverse=reverse,
        )

    @staticmethod
    def _sort_value(
        *,
        record: ApplicationGuardrailRecord,
        field: ApplicationGuardrailSortField,
    ) -> Any:
        """Return one comparable sort value."""

        if field is ApplicationGuardrailSortField.EVALUATED_AT:
            return record.evaluated_at

        if (
            field
            is ApplicationGuardrailSortField.TOTAL_VIOLATIONS
        ):
            return record.total_violation_count

        if (
            field
            is ApplicationGuardrailSortField
            .BLOCKING_VIOLATIONS
        ):
            return record.blocking_violation_count

        return record.record_version

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize one identifier."""

        return value.strip().casefold()

    @classmethod
    def _matches_optional_id(
        cls,
        *,
        actual: str | None,
        expected: str | None,
    ) -> bool:
        """Match an optional identifier query."""

        if expected is None:
            return True

        if actual is None:
            return False

        return cls._normalize_id(
            actual
        ) == cls._normalize_id(expected)
