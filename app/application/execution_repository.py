"""Repository interface for persistent application executions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.execution_record import (
    ApplicationExecutionRecord,
)
from app.application.execution_repository_error import (
    ApplicationExecutionNotFoundError,
)
from app.application.execution_repository_query import (
    ApplicationExecutionPage,
    ApplicationExecutionQuery,
)


class ApplicationExecutionRepository(ABC):
    """Persistence contract for application execution records."""

    @abstractmethod
    def create(
        self,
        record: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        """Persist a new execution record.

        Raises:
            ApplicationExecutionAlreadyExistsError:
                The execution ID already exists.
        """

    @abstractmethod
    def get(
        self,
        execution_id: str,
    ) -> ApplicationExecutionRecord | None:
        """Return an execution record or None."""

    def require(
        self,
        execution_id: str,
    ) -> ApplicationExecutionRecord:
        """Return one execution record or raise not-found."""

        record = self.get(execution_id)

        if record is None:
            raise ApplicationExecutionNotFoundError(
                "application execution was not found: "
                f"{execution_id}"
            )

        return record

    @abstractmethod
    def update(
        self,
        record: ApplicationExecutionRecord,
        *,
        expected_version: int,
    ) -> ApplicationExecutionRecord:
        """Replace a record using optimistic concurrency.

        The stored record version must equal expected_version.
        The returned record must have a version greater than the
        stored version.

        Raises:
            ApplicationExecutionNotFoundError:
                The execution record does not exist.
            ApplicationExecutionVersionConflictError:
                The expected version does not match.
        """

    @abstractmethod
    def list(
        self,
        query: ApplicationExecutionQuery,
    ) -> ApplicationExecutionPage:
        """Return a filtered and paginated execution page."""

    @abstractmethod
    def count(
        self,
        query: ApplicationExecutionQuery,
    ) -> int:
        """Return the number of records matching a query."""

    def exists(
        self,
        execution_id: str,
    ) -> bool:
        """Return whether one execution record exists."""

        return self.get(execution_id) is not None
