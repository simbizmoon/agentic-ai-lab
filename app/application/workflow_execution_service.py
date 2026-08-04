"""Application service for synchronous workflow execution."""

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
from app.application.workflow_execution import (
    ApplicationWorkflowExecutionRequest,
    ApplicationWorkflowExecutionResult,
    WorkflowExecutionRunner,
)
from app.application.workflow_execution_service_error import (
    ApplicationWorkflowExecutionFailedError,
    ApplicationWorkflowExecutionServiceError,
)


class ApplicationWorkflowExecutionService:
    """Persist and execute one synchronous workflow."""

    def __init__(
        self,
        *,
        execution_repository: ApplicationExecutionRepository,
        runner: WorkflowExecutionRunner,
        clock: Callable[[], datetime],
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._execution_repository = execution_repository
        self._runner = runner
        self._clock = clock
        self._execution_id_factory = (
            execution_id_factory
            or (lambda: f"workflow-execution-{uuid4()}")
        )

    def execute(
        self,
        request: ApplicationWorkflowExecutionRequest,
    ) -> ApplicationWorkflowExecutionResult:
        """Execute and persist one workflow lifecycle."""

        execution_id = self._new_execution_id()
        created_at = self._now()

        pending = ApplicationExecutionRecord(
            execution_id=execution_id,
            root_execution_id=(
                request.root_execution_id or execution_id
            ),
            parent_execution_id=(
                request.parent_execution_id
            ),
            previous_attempt_execution_id=(
                request.previous_attempt_execution_id
            ),
            request_id=request.request_id,
            workspace_id=request.workspace_id,
            subject_type=(
                ApplicationExecutionSubjectType.WORKFLOW
            ),
            subject_id=request.workflow_id,
            status=ApplicationExecutionStatus.PENDING,
            attempt_number=request.attempt_number,
            maximum_attempts=request.maximum_attempts,
            created_at=created_at,
        )

        stored = self._execution_repository.create(pending)
        running = self._mark_running(stored)

        try:
            output = self._runner.execute(request)
        except ValueError as error:
            failed = self._mark_failed(
                running,
                error=error,
                category=(
                    ApplicationExecutionFailureCategory.VALIDATION
                ),
            )
            self._raise_failed(failed)
        except RuntimeError as error:
            failed = self._mark_failed(
                running,
                error=error,
                category=(
                    ApplicationExecutionFailureCategory.INTERNAL
                ),
            )
            self._raise_failed(failed)

        succeeded = self._mark_succeeded(running)

        return ApplicationWorkflowExecutionResult(
            execution=succeeded,
            output=output,
        )

    def _mark_running(
        self,
        stored: ApplicationExecutionRecord,
    ) -> ApplicationExecutionRecord:
        """Change a pending workflow to running."""

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
        """Change a running workflow to succeeded."""

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
        error: ValueError | RuntimeError,
        category: ApplicationExecutionFailureCategory,
    ) -> ApplicationExecutionRecord:
        """Persist a failed workflow execution."""

        ApplicationExecutionTransitionPolicy.require_transition(
            current=running.status,
            target=ApplicationExecutionStatus.FAILED,
        )

        failure = ApplicationExecutionFailure(
            category=category,
            code=type(error).__name__,
            message=str(error) or "Workflow execution failed.",
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

    @staticmethod
    def _raise_failed(
        failed: ApplicationExecutionRecord,
    ) -> None:
        """Raise a public workflow failure."""

        assert failed.failure is not None

        raise ApplicationWorkflowExecutionFailedError(
            execution_id=failed.execution_id,
            failure_code=failed.failure.code,
            message=failed.failure.message,
        )

    def _now(self) -> datetime:
        """Return a validated application timestamp."""

        value = self._clock()

        if value.tzinfo is None:
            raise ApplicationWorkflowExecutionServiceError(
                "clock must return timezone-aware datetime"
            )

        return value

    def _new_execution_id(self) -> str:
        """Return one nonblank execution ID."""

        value = self._execution_id_factory()

        if not value.strip():
            raise ApplicationWorkflowExecutionServiceError(
                "execution ID factory returned blank value"
            )

        return value
