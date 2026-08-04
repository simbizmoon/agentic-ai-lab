"""Repository interface for persistent guardrail results."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.guardrail_record import (
    ApplicationGuardrailRecord,
)
from app.application.guardrail_repository_error import (
    ApplicationGuardrailNotFoundError,
)
from app.application.guardrail_repository_query import (
    ApplicationGuardrailPage,
    ApplicationGuardrailQuery,
)


class ApplicationGuardrailRepository(ABC):
    """Persistence contract for guardrail evaluation records."""

    @abstractmethod
    def create(
        self,
        record: ApplicationGuardrailRecord,
    ) -> ApplicationGuardrailRecord:
        """Persist a new guardrail evaluation."""

    @abstractmethod
    def get(
        self,
        guardrail_evaluation_id: str,
    ) -> ApplicationGuardrailRecord | None:
        """Return a guardrail record or None."""

    def require(
        self,
        guardrail_evaluation_id: str,
    ) -> ApplicationGuardrailRecord:
        """Return one guardrail record or raise not-found."""

        record = self.get(guardrail_evaluation_id)

        if record is None:
            raise ApplicationGuardrailNotFoundError(
                "application guardrail evaluation was not "
                f"found: {guardrail_evaluation_id}"
            )

        return record

    @abstractmethod
    def update(
        self,
        record: ApplicationGuardrailRecord,
        *,
        expected_version: int,
    ) -> ApplicationGuardrailRecord:
        """Replace a record using optimistic concurrency."""

    @abstractmethod
    def list(
        self,
        query: ApplicationGuardrailQuery,
    ) -> ApplicationGuardrailPage:
        """Return filtered and paginated guardrail results."""

    @abstractmethod
    def count(
        self,
        query: ApplicationGuardrailQuery,
    ) -> int:
        """Return the number of matching guardrail records."""

    def exists(
        self,
        guardrail_evaluation_id: str,
    ) -> bool:
        """Return whether one guardrail result exists."""

        return self.get(guardrail_evaluation_id) is not None
