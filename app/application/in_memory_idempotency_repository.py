"""In-memory application idempotency repository."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock

from app.application.idempotency_record import (
    ApplicationIdempotencyRecord,
)
from app.application.idempotency_repository import (
    ApplicationIdempotencyRepository,
)
from app.application.idempotency_repository_error import (
    ApplicationIdempotencyAlreadyExistsError,
    ApplicationIdempotencyNotFoundError,
    ApplicationIdempotencyVersionConflictError,
)


class InMemoryApplicationIdempotencyRepository(
    ApplicationIdempotencyRepository
):
    """Store idempotency records in process memory."""

    def __init__(
        self,
        records: list[ApplicationIdempotencyRecord] | None = None,
    ) -> None:
        self._records: dict[str, ApplicationIdempotencyRecord] = {}
        self._identity_index: dict[
            tuple[str, str, str],
            str,
        ] = {}
        self._lock = RLock()

        for record in records or []:
            self.create(record)

    def create(
        self,
        record: ApplicationIdempotencyRecord,
    ) -> ApplicationIdempotencyRecord:
        """Persist a new record."""

        key = self._normalize(record.idempotency_record_id)
        identity = self._identity(record)

        with self._lock:
            if key in self._records or identity in self._identity_index:
                raise ApplicationIdempotencyAlreadyExistsError(
                    "application idempotency identity already exists"
                )

            self._records[key] = record
            self._identity_index[identity] = key

        return record

    def get(
        self,
        idempotency_record_id: str,
    ) -> ApplicationIdempotencyRecord | None:
        """Return one record or None."""

        key = self._normalize(idempotency_record_id)

        with self._lock:
            return self._records.get(key)

    def find(
        self,
        *,
        workspace_id: str,
        operation: str,
        idempotency_key: str,
    ) -> ApplicationIdempotencyRecord | None:
        """Find a record by logical identity."""

        identity = (
            self._normalize(workspace_id),
            self._normalize(operation),
            self._normalize(idempotency_key),
        )

        with self._lock:
            record_key = self._identity_index.get(identity)

            if record_key is None:
                return None

            return self._records[record_key]

    def update(
        self,
        record: ApplicationIdempotencyRecord,
        *,
        expected_version: int,
    ) -> ApplicationIdempotencyRecord:
        """Replace a record using optimistic concurrency."""

        key = self._normalize(record.idempotency_record_id)

        with self._lock:
            stored = self._records.get(key)

            if stored is None:
                raise ApplicationIdempotencyNotFoundError(
                    "application idempotency record was not found: "
                    f"{record.idempotency_record_id}"
                )

            if stored.record_version != expected_version:
                raise ApplicationIdempotencyVersionConflictError(
                    "application idempotency version conflict: "
                    f"expected {expected_version}, "
                    f"stored {stored.record_version}"
                )

            if record.record_version != expected_version + 1:
                raise ApplicationIdempotencyVersionConflictError(
                    "updated idempotency record_version must "
                    f"equal {expected_version + 1}"
                )

            if self._identity(record) != self._identity(stored):
                raise ApplicationIdempotencyVersionConflictError(
                    "idempotency identity cannot be changed"
                )

            self._records[key] = record

        return record

    def snapshot_state(
        self,
    ) -> tuple[
        dict[str, ApplicationIdempotencyRecord],
        dict[tuple[str, str, str], str],
    ]:
        """Return an isolated repository snapshot."""

        with self._lock:
            return (
                deepcopy(self._records),
                deepcopy(self._identity_index),
            )

    def restore_state(
        self,
        snapshot: tuple[
            dict[str, ApplicationIdempotencyRecord],
            dict[tuple[str, str, str], str],
        ],
    ) -> None:
        """Restore a previously captured snapshot."""

        with self._lock:
            self._records = deepcopy(snapshot[0])
            self._identity_index = deepcopy(snapshot[1])

    @classmethod
    def _identity(
        cls,
        record: ApplicationIdempotencyRecord,
    ) -> tuple[str, str, str]:
        """Return the unique logical identity."""

        return (
            cls._normalize(record.workspace_id),
            cls._normalize(record.operation),
            cls._normalize(record.idempotency_key),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a repository identifier."""

        return value.strip().casefold()
