"""Repository interface for persisted cancellation requests."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.cancellation_record import (
    ApplicationJobCancellationRequestRecord,
)
from app.application.cancellation_repository_error import (
    ApplicationCancellationNotFoundError,
)


class ApplicationCancellationRepository(ABC):
    """Persistence contract for job cancellation requests."""

    @abstractmethod
    def create(
        self,
        record: ApplicationJobCancellationRequestRecord,
    ) -> ApplicationJobCancellationRequestRecord:
        """Persist a new cancellation request."""

    @abstractmethod
    def get(
        self,
        cancellation_request_id: str,
    ) -> ApplicationJobCancellationRequestRecord | None:
        """Return one cancellation request or None."""

    def require(
        self,
        cancellation_request_id: str,
    ) -> ApplicationJobCancellationRequestRecord:
        """Return one request or raise not-found."""

        record = self.get(cancellation_request_id)

        if record is None:
            raise ApplicationCancellationNotFoundError(
                "application cancellation request was not "
                f"found: {cancellation_request_id}"
            )

        return record

    @abstractmethod
    def update(
        self,
        record: ApplicationJobCancellationRequestRecord,
        *,
        expected_version: int,
    ) -> ApplicationJobCancellationRequestRecord:
        """Replace a request using optimistic concurrency."""

    @abstractmethod
    def find_by_job_id(
        self,
        job_id: str,
    ) -> list[ApplicationJobCancellationRequestRecord]:
        """Return cancellation requests for one job."""

    def find_active_by_job_id(
        self,
        job_id: str,
    ) -> ApplicationJobCancellationRequestRecord | None:
        """Return the active cancellation request for a job."""

        for record in self.find_by_job_id(job_id):
            if not record.terminal:
                return record

        return None
