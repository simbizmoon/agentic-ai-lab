"""Application service for synchronous research execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from app.application.execution_record import (
    ApplicationExecutionFailure,
    ApplicationExecutionFailureCategory,
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.execution_repository import (
    ApplicationExecutionRepository,
)
from app.application.execution_transition import (
    ApplicationExecutionTransitionPolicy,
)
from app.application.research_execution import (
    ApplicationResearchExecutionRequest,
    ApplicationResearchExecutionResult,
    ResearchExecutionRunner,
)
from app.application.research_execution_service_error import (
    ApplicationResearchExecutionFailedError,
    ApplicationResearchExecutionServiceError,
)


class ApplicationResearchExecutionService:
    """Persist and execute one synchronous research request."""

    def __init__(
        self,
        *,
        execution_repository: ApplicationExecutionRepository,
        runner: ResearchExecutionRunner,
        clock: Callable[[], datetime],
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._execution_repository = execution_repository
        self._runner = runner
        self._clock = clock
        self._execution_id_factory = (
            execution_id_factory
            or (lambda: f"research-execution-{uuid4()}")
        )

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionResult:
        """Execute research and persist its lifecycle."""

        execution_id = self._new_execution_id()
        created_at = self._now()

        root_execution_id = (
            request.root_execution_id or execution_id
        )

        pending = ApplicationExecutionRecord(
            execution_id=execution_id,
            root_execution_id=root_execution_id,
            parent_execution_id=(
                request.parent_execution_id
            ),
            previous_attempt_execution_id=(
                request.previous_attempt_execution_id
            ),
            request_id=request.request_id,
            workspace_id=request.workspace_id,
            subject_type=(
                ApplicationExecutionSubjectType.AGENT
            ),
            subject_id=request.agent_id,
            status=ApplicationExecutionStatus.PENDING,
            attempt_number=request.attempt_number,
            maximum_attempts=request.maximum_attempts,
            created_at=created_at,
        )

        stored = self._execution_repository.create(pending)
        running = self._mark_running(stored)

        try:
            output = self._runner.execute(request)
        except (RuntimeError, ValueError) as error:
            failed = self._mark_failed(
                running,
                error=error,
            )

            raise ApplicationResearchExecutionFailedError(
                execution_id=failed.execution_id,
                message=str(error),
            ) from error

        succeeded = self._mark_succeeded(running)

        return ApplicationResearchExecutionResult(
            execution=succeeded,
            output=output,
        )

    def _mark_running(
        self,
        stored: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        """Change a pending execution to running."""

        ApplicationExecutionTransitionPolicy.require_transition(
            current=stored.status,
            target=ApplicationExecutionStatus.RUNNING,
        )

        running = stored.model_copy(
            update={
                "status": ApplicationExecutionStatus.RUNNING,
                "started_at": self._now(),
                "record_version": stored.record_version + 1,
            }
        )

        return self._execution_repository.update(
            running,
            expected_version=stored.record_version,
        )

    def _mark_succeeded(
        self,
        running: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        """Change a running execution to succeeded."""

        ApplicationExecutionTransitionPolicy.require_transition(
            current=running.status,
            target=ApplicationExecutionStatus.SUCCEEDED,
        )

        succeeded = running.model_copy(
            update={
                "status": (
                    ApplicationExecutionStatus.SUCCEEDED
                ),
                "finished_at": self._now(),
                "record_version": (
                    running.record_version + 1
                ),
            }
        )

        return self._execution_repository.update(
            succeeded,
            expected_version=running.record_version,
        )

    def _mark_failed(
        self,
        running: ApplicationExecutionRecord,
        *,
        error: RuntimeError | ValueError,
    ) -> ApplicationExecutionRecord:
        """Persist a failed research execution."""

        ApplicationExecutionTransitionPolicy.require_transition(
            current=running.status,
            target=ApplicationExecutionStatus.FAILED,
        )

        failure = ApplicationExecutionFailure(
            category=(
                ApplicationExecutionFailureCategory.INTERNAL
            ),
            code=type(error).__name__,
            message=str(error) or "Research execution failed.",
            retryable=False,
        )

        failed = running.model_copy(
            update={
                "status": ApplicationExecutionStatus.FAILED,
                "finished_at": self._now(),
                "failure": failure,
                "record_version": (
                    running.record_version + 1
                ),
            }
        )

        return self._execution_repository.update(
            failed,
            expected_version=running.record_version,
        )

    def _now(self) -> datetime:
        """Return a validated application timestamp."""

        value = self._clock()

        if value.tzinfo is None:
            raise ApplicationResearchExecutionServiceError(
                "clock must return timezone-aware datetime"
            )

        return value

    def _new_execution_id(self) -> str:
        """Return one nonblank execution identifier."""

        value = self._execution_id_factory()

        if not value.strip():
            raise ApplicationResearchExecutionServiceError(
                "execution ID factory returned blank value"
            )

        return value
