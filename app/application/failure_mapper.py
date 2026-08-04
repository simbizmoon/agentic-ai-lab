"""Map application exceptions to normalized failures."""

from __future__ import annotations

from pydantic import ValidationError

from app.application.cancellation_repository_error import (
    ApplicationCancellationAlreadyExistsError,
    ApplicationCancellationNotFoundError,
    ApplicationCancellationVersionConflictError,
)
from app.application.cancellation_service_error import (
    ApplicationCancellationAlreadyActiveError,
    ApplicationCancellationServiceError,
    ApplicationCancellationStateError,
    ApplicationJobCannotBeCancelledError,
)
from app.application.execution_repository_error import (
    ApplicationExecutionAlreadyExistsError,
    ApplicationExecutionNotFoundError,
    ApplicationExecutionVersionConflictError,
)
from app.application.failure import (
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationFailureDetail,
)
from app.application.idempotency_repository_error import (
    ApplicationIdempotencyAlreadyExistsError,
    ApplicationIdempotencyNotFoundError,
    ApplicationIdempotencyVersionConflictError,
)
from app.application.idempotency_service_error import (
    ApplicationIdempotencyConflictError,
    ApplicationIdempotencyInProgressError,
    ApplicationIdempotencyRetryNotAllowedError,
)
from app.application.job_repository_error import (
    ApplicationJobAlreadyExistsError,
    ApplicationJobNotFoundError,
    ApplicationJobVersionConflictError,
)
from app.application.research_execution_service_error import (
    ApplicationResearchExecutionFailedError,
)
from app.application.tool_execution_service_error import (
    ApplicationToolExecutionFailedError,
)
from app.application.workflow_execution_service_error import (
    ApplicationWorkflowExecutionFailedError,
)


class ApplicationFailureMapper:
    """Convert raw exceptions to stable application failures."""

    def map(
        self,
        error: BaseException,
    ) -> ApplicationFailure:
        """Return a normalized failure for one exception."""

        if isinstance(error, ValidationError):
            return self._map_validation(error)

        if isinstance(
            error,
            (
                ApplicationExecutionNotFoundError,
                ApplicationJobNotFoundError,
                ApplicationCancellationNotFoundError,
                ApplicationIdempotencyNotFoundError,
            ),
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.NOT_FOUND,
                code="RESOURCE_NOT_FOUND",
                message="The requested resource was not found.",
                retryable=False,
                status_code=404,
            )

        if isinstance(
            error,
            (
                ApplicationExecutionAlreadyExistsError,
                ApplicationJobAlreadyExistsError,
                ApplicationCancellationAlreadyExistsError,
                ApplicationIdempotencyAlreadyExistsError,
                ApplicationCancellationAlreadyActiveError,
                ApplicationIdempotencyConflictError,
                ApplicationIdempotencyRetryNotAllowedError,
                ApplicationJobCannotBeCancelledError,
                ApplicationCancellationStateError,
            ),
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.CONFLICT,
                code="APPLICATION_CONFLICT",
                message=(
                    "The operation conflicts with the "
                    "current resource state."
                ),
                retryable=False,
                status_code=409,
            )

        if isinstance(
            error,
            (
                ApplicationExecutionVersionConflictError,
                ApplicationJobVersionConflictError,
                ApplicationCancellationVersionConflictError,
                ApplicationIdempotencyVersionConflictError,
            ),
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.CONFLICT,
                code="VERSION_CONFLICT",
                message=(
                    "The resource changed while the "
                    "operation was being processed."
                ),
                retryable=True,
                status_code=409,
            )

        if isinstance(
            error,
            ApplicationIdempotencyInProgressError,
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.CONFLICT,
                code="OPERATION_IN_PROGRESS",
                message=(
                    "The same operation is already in progress."
                ),
                retryable=True,
                status_code=409,
            )

        if isinstance(error, PermissionError):
            return self._failure(
                error,
                category=ApplicationFailureCategory.PERMISSION,
                code="PERMISSION_DENIED",
                message=(
                    "You do not have permission to perform "
                    "this operation."
                ),
                retryable=False,
                status_code=403,
            )

        if isinstance(
            error,
            ApplicationResearchExecutionFailedError,
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.EXECUTION,
                code="RESEARCH_EXECUTION_FAILED",
                message="The research execution failed.",
                retryable=False,
                status_code=500,
                execution_id=error.execution_id,
                metadata={
                    "failure_message": error.failure_message,
                },
            )

        if isinstance(
            error,
            ApplicationToolExecutionFailedError,
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.EXECUTION,
                code=error.failure_code,
                message="The tool execution failed.",
                retryable=False,
                status_code=500,
                execution_id=error.execution_id,
                metadata={
                    "failure_message": error.failure_message,
                },
            )

        if isinstance(
            error,
            ApplicationWorkflowExecutionFailedError,
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.EXECUTION,
                code=error.failure_code,
                message="The workflow execution failed.",
                retryable=False,
                status_code=500,
                execution_id=error.execution_id,
                metadata={
                    "failure_message": error.failure_message,
                },
            )

        if isinstance(error, TimeoutError):
            return self._failure(
                error,
                category=ApplicationFailureCategory.TIMEOUT,
                code="OPERATION_TIMEOUT",
                message="The operation timed out.",
                retryable=True,
                status_code=504,
            )

        if isinstance(error, InterruptedError):
            return self._failure(
                error,
                category=ApplicationFailureCategory.CANCELLED,
                code="OPERATION_CANCELLED",
                message="The operation was cancelled.",
                retryable=False,
                status_code=409,
            )

        if isinstance(
            error,
            ApplicationCancellationServiceError,
        ):
            return self._failure(
                error,
                category=ApplicationFailureCategory.CONFLICT,
                code="CANCELLATION_ERROR",
                message=(
                    "The cancellation operation could not "
                    "be completed."
                ),
                retryable=False,
                status_code=409,
            )

        return self._failure(
            error,
            category=ApplicationFailureCategory.INTERNAL,
            code="INTERNAL_ERROR",
            message=(
                "An unexpected internal error occurred."
            ),
            retryable=False,
            status_code=500,
        )

    def _map_validation(
        self,
        error: ValidationError,
    ) -> ApplicationFailure:
        """Map a Pydantic validation error."""

        details: list[ApplicationFailureDetail] = []

        for item in error.errors():
            location = ".".join(
                str(part)
                for part in item.get("loc", ())
            )

            details.append(
                ApplicationFailureDetail(
                    location=location or "request",
                    code=str(
                        item.get("type", "validation_error")
                    ),
                    message=str(
                        item.get(
                            "msg",
                            "Input validation failed.",
                        )
                    ),
                    context=self._safe_context(
                        item.get("ctx")
                    ),
                )
            )

        return ApplicationFailure(
            category=ApplicationFailureCategory.VALIDATION,
            code="VALIDATION_ERROR",
            message="The request data is invalid.",
            retryable=False,
            status_code=422,
            details=self._deduplicate_details(details),
            internal_message=str(error),
            exception_type=type(error).__name__,
        )

    @staticmethod
    def _safe_context(
        value: object,
    ) -> dict[str, str | int | float | bool | None]:
        """Return JSON-compatible validation context."""

        if not isinstance(value, dict):
            return {}

        result: dict[
            str,
            str | int | float | bool | None,
        ] = {}

        for key, item in value.items():
            normalized_key = str(key)

            if item is None or isinstance(
                item,
                (str, int, float, bool),
            ):
                result[normalized_key] = item
            else:
                result[normalized_key] = str(item)

        return result

    @staticmethod
    def _deduplicate_details(
        details: list[ApplicationFailureDetail],
    ) -> list[ApplicationFailureDetail]:
        """Keep the first detail for each normalized location."""

        unique: dict[str, ApplicationFailureDetail] = {}

        for detail in details:
            key = detail.location.strip().casefold()
            unique.setdefault(key, detail)

        return list(unique.values())

    @staticmethod
    def _failure(
        error: BaseException,
        *,
        category: ApplicationFailureCategory,
        code: str,
        message: str,
        retryable: bool,
        status_code: int,
        execution_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ApplicationFailure:
        """Build one normalized application failure."""

        internal_message = str(error).strip()

        return ApplicationFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            status_code=status_code,
            internal_message=(
                internal_message
                if internal_message
                else type(error).__name__
            ),
            exception_type=type(error).__name__,
            execution_id=execution_id,
            metadata=metadata or {},
        )
