"""Repository interface for persistent evaluation results."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.evaluation_record import (
    ApplicationEvaluationRecord,
)
from app.application.evaluation_repository_error import (
    ApplicationEvaluationNotFoundError,
)
from app.application.evaluation_repository_query import (
    ApplicationEvaluationPage,
    ApplicationEvaluationQuery,
)


class ApplicationEvaluationRepository(ABC):
    """Persistence contract for evaluation result records."""

    @abstractmethod
    def create(
        self,
        record: ApplicationEvaluationRecord,
    ) -> ApplicationEvaluationRecord:
        """Persist a new evaluation record."""

    @abstractmethod
    def get(
        self,
        evaluation_id: str,
    ) -> ApplicationEvaluationRecord | None:
        """Return an evaluation record or None."""

    def require(
        self,
        evaluation_id: str,
    ) -> ApplicationEvaluationRecord:
        """Return one evaluation record or raise not-found."""

        record = self.get(evaluation_id)

        if record is None:
            raise ApplicationEvaluationNotFoundError(
                "application evaluation was not found: "
                f"{evaluation_id}"
            )

        return record

    @abstractmethod
    def update(
        self,
        record: ApplicationEvaluationRecord,
        *,
        expected_version: int,
    ) -> ApplicationEvaluationRecord:
        """Replace a record using optimistic concurrency."""

    @abstractmethod
    def list(
        self,
        query: ApplicationEvaluationQuery,
    ) -> ApplicationEvaluationPage:
        """Return filtered and paginated evaluations."""

    @abstractmethod
    def count(
        self,
        query: ApplicationEvaluationQuery,
    ) -> int:
        """Return the number of matching evaluations."""

    def exists(
        self,
        evaluation_id: str,
    ) -> bool:
        """Return whether an evaluation exists."""

        return self.get(evaluation_id) is not None
