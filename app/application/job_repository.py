"""Repository interface for persistent background jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.application.job_record import (
    ApplicationJobRecord,
)
from app.application.job_repository_error import (
    ApplicationJobNotFoundError,
)
from app.application.job_repository_query import (
    ApplicationJobPage,
    ApplicationJobQuery,
)


class ApplicationJobRepository(ABC):
    """Persistence contract for background-job records."""

    @abstractmethod
    def create(
        self,
        record: ApplicationJobRecord,
    ) -> ApplicationJobRecord:
        """Persist a new background job."""

    @abstractmethod
    def get(
        self,
        job_id: str,
    ) -> ApplicationJobRecord | None:
        """Return one job record or None."""

    def require(
        self,
        job_id: str,
    ) -> ApplicationJobRecord:
        """Return one job record or raise not-found."""

        record = self.get(job_id)

        if record is None:
            raise ApplicationJobNotFoundError(
                "application job was not found: "
                f"{job_id}"
            )

        return record

    @abstractmethod
    def update(
        self,
        record: ApplicationJobRecord,
        *,
        expected_version: int,
    ) -> ApplicationJobRecord:
        """Replace a job using optimistic concurrency."""

    @abstractmethod
    def list(
        self,
        query: ApplicationJobQuery,
    ) -> ApplicationJobPage:
        """Return filtered and paginated jobs."""

    @abstractmethod
    def count(
        self,
        query: ApplicationJobQuery,
    ) -> int:
        """Return the number of matching jobs."""

    @abstractmethod
    def find_available(
        self,
        *,
        queue_name: str,
        now: datetime,
        limit: int = 1,
    ) -> list[ApplicationJobRecord]:
        """Return executable jobs ordered for worker pickup."""

    def exists(
        self,
        job_id: str,
    ) -> bool:
        """Return whether one job exists."""

        return self.get(job_id) is not None
