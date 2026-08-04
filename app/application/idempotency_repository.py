"""Repository contract for application idempotency records."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.idempotency_record import (
    ApplicationIdempotencyRecord,
)
from app.application.idempotency_repository_error import (
    ApplicationIdempotencyNotFoundError,
)


class ApplicationIdempotencyRepository(ABC):
    """Persistence contract for idempotency records."""

    @abstractmethod
    def create(
        self,
        record: ApplicationIdempotencyRecord,
    ) -> ApplicationIdempotencyRecord:
        """Persist a new record."""

    @abstractmethod
    def get(
        self,
        idempotency_record_id: str,
    ) -> ApplicationIdempotencyRecord | None:
        """Return one record or None."""

    def require(
        self,
        idempotency_record_id: str,
    ) -> ApplicationIdempotencyRecord:
        """Return one record or raise not-found."""

        record = self.get(idempotency_record_id)

        if record is None:
            raise ApplicationIdempotencyNotFoundError(
                "application idempotency record was not found: "
                f"{idempotency_record_id}"
            )

        return record

    @abstractmethod
    def find(
        self,
        *,
        workspace_id: str,
        operation: str,
        idempotency_key: str,
    ) -> ApplicationIdempotencyRecord | None:
        """Find a record by its unique logical identity."""

    @abstractmethod
    def update(
        self,
        record: ApplicationIdempotencyRecord,
        *,
        expected_version: int,
    ) -> ApplicationIdempotencyRecord:
        """Replace a record using optimistic concurrency."""
