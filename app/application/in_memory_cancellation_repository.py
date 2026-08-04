"""In-memory cancellation request repository."""

from __future__ import annotations

from threading import RLock

from app.application.cancellation_record import (
    ApplicationJobCancellationRequestRecord,
)
from app.application.cancellation_repository import (
    ApplicationCancellationRepository,
)
from app.application.cancellation_repository_error import (
    ApplicationCancellationAlreadyExistsError,
    ApplicationCancellationNotFoundError,
    ApplicationCancellationVersionConflictError,
)


class InMemoryApplicationCancellationRepository(
    ApplicationCancellationRepository
):
    """Store cancellation requests in process memory."""

    def __init__(
        self,
        records: list[
            ApplicationJobCancellationRequestRecord
        ]
        | None = None,
    ) -> None:
        self._records: dict[
            str,
            ApplicationJobCancellationRequestRecord,
        ] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationJobCancellationRequestRecord,
    ) -> ApplicationJobCancellationRequestRecord:
        """Persist a new cancellation request."""

        key = self._normalize_id(
            record.cancellation_request_id
        )

        with self._lock:
            if key in self._records:
                raise ApplicationCancellationAlreadyExistsError(
                    "application cancellation request already "
                    f"exists: {record.cancellation_request_id}"
                )

            self._records[key] = record

        return record

    def get(
        self,
        cancellation_request_id: str,
    ) -> ApplicationJobCancellationRequestRecord | None:
        """Return one cancellation request or None."""

        key = self._normalize_id(
            cancellation_request_id
        )

        with self._lock:
            return self._records.get(key)

    def update(
        self,
        record: ApplicationJobCancellationRequestRecord,
        *,
        expected_version: int,
    ) -> ApplicationJobCancellationRequestRecord:
        """Replace a request using optimistic concurrency."""

        if expected_version < 1:
            raise ApplicationCancellationVersionConflictError(
                "expected_version must be at least 1"
            )

        key = self._normalize_id(
            record.cancellation_request_id
        )

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationCancellationNotFoundError(
                    "application cancellation request was not "
                    f"found: {record.cancellation_request_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationCancellationVersionConflictError(
                    "application cancellation version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            required_version = expected_version + 1

            if record.record_version != required_version:
                raise ApplicationCancellationVersionConflictError(
                    "updated cancellation record_version must "
                    f"equal {required_version}"
                )

            self._records[key] = record

        return record

    def find_by_job_id(
        self,
        job_id: str,
    ) -> list[ApplicationJobCancellationRequestRecord]:
        """Return requests for one Job ID."""

        normalized_job_id = self._normalize_id(job_id)

        with self._lock:
            records = [
                record
                for record in self._records.values()
                if self._normalize_id(record.job_id)
                == normalized_job_id
            ]

        return sorted(
            records,
            key=lambda record: (
                record.requested_at,
                self._normalize_id(
                    record.cancellation_request_id
                ),
            ),
            reverse=True,
        )

    def clear(self) -> None:
        """Remove all cancellation requests."""

        with self._lock:
            self._records.clear()

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize a repository identifier."""

        return value.strip().casefold()
