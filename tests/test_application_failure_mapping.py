"""Tests for application failure normalization."""

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.application.execution_repository_error import (
    ApplicationExecutionNotFoundError,
    ApplicationExecutionVersionConflictError,
)
from app.application.failure import (
    ApplicationFailureCategory,
)
from app.application.failure_mapper import (
    ApplicationFailureMapper,
)
from app.application.failure_response import (
    ApplicationFailureResponse,
)
from app.application.idempotency_service_error import (
    ApplicationIdempotencyConflictError,
    ApplicationIdempotencyInProgressError,
)
from app.application.tool_execution_service_error import (
    ApplicationToolExecutionFailedError,
)


class StrictRequest(BaseModel):
    """Small strict request used to trigger validation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    query: str
    limit: int


def mapper() -> ApplicationFailureMapper:
    """Return one application failure mapper."""

    return ApplicationFailureMapper()


def test_validation_error_maps_to_422() -> None:
    with pytest.raises(ValidationError) as captured:
        StrictRequest.model_validate(
            {
                "query": "research",
                "limit": "5",
            }
        )

    failure = mapper().map(captured.value)

    assert failure.category is (
        ApplicationFailureCategory.VALIDATION
    )
    assert failure.code == "VALIDATION_ERROR"
    assert failure.status_code == 422
    assert failure.retryable is False
    assert len(failure.details) == 1
    assert failure.details[0].location == "limit"


def test_not_found_maps_to_404() -> None:
    failure = mapper().map(
        ApplicationExecutionNotFoundError(
            "execution was not found"
        )
    )

    assert failure.category is (
        ApplicationFailureCategory.NOT_FOUND
    )
    assert failure.code == "RESOURCE_NOT_FOUND"
    assert failure.status_code == 404
    assert failure.retryable is False


def test_version_conflict_is_retryable() -> None:
    failure = mapper().map(
        ApplicationExecutionVersionConflictError(
            "stored version changed"
        )
    )

    assert failure.category is (
        ApplicationFailureCategory.CONFLICT
    )
    assert failure.code == "VERSION_CONFLICT"
    assert failure.status_code == 409
    assert failure.retryable is True


def test_idempotency_payload_conflict_maps_to_409() -> None:
    failure = mapper().map(
        ApplicationIdempotencyConflictError(
            "different payload"
        )
    )

    assert failure.category is (
        ApplicationFailureCategory.CONFLICT
    )
    assert failure.code == "APPLICATION_CONFLICT"
    assert failure.status_code == 409
    assert failure.retryable is False


def test_in_progress_operation_is_retryable() -> None:
    failure = mapper().map(
        ApplicationIdempotencyInProgressError(
            "operation is active"
        )
    )

    assert failure.code == "OPERATION_IN_PROGRESS"
    assert failure.status_code == 409
    assert failure.retryable is True


def test_permission_error_maps_to_403() -> None:
    failure = mapper().map(
        PermissionError("tool permission denied")
    )

    assert failure.category is (
        ApplicationFailureCategory.PERMISSION
    )
    assert failure.code == "PERMISSION_DENIED"
    assert failure.status_code == 403


def test_tool_execution_failure_preserves_execution_id() -> None:
    failure = mapper().map(
        ApplicationToolExecutionFailedError(
            execution_id="tool-execution-001",
            failure_code="TOOL_PROVIDER_ERROR",
            message="Provider unavailable.",
        )
    )

    assert failure.category is (
        ApplicationFailureCategory.EXECUTION
    )
    assert failure.code == "TOOL_PROVIDER_ERROR"
    assert failure.execution_id == "tool-execution-001"
    assert failure.metadata["failure_message"] == (
        "Provider unavailable."
    )


def test_timeout_is_retryable() -> None:
    failure = mapper().map(
        TimeoutError("request timed out")
    )

    assert failure.category is (
        ApplicationFailureCategory.TIMEOUT
    )
    assert failure.code == "OPERATION_TIMEOUT"
    assert failure.status_code == 504
    assert failure.retryable is True


def test_unknown_error_is_safely_mapped() -> None:
    failure = mapper().map(
        RuntimeError("database password leaked internally")
    )

    assert failure.category is (
        ApplicationFailureCategory.INTERNAL
    )
    assert failure.code == "INTERNAL_ERROR"
    assert failure.message == (
        "An unexpected internal error occurred."
    )
    assert failure.internal_message == (
        "database password leaked internally"
    )
    assert failure.status_code == 500


def test_public_response_hides_internal_message() -> None:
    failure = mapper().map(
        RuntimeError("internal database detail")
    )

    response = ApplicationFailureResponse.from_failure(
        failure
    )

    error = response.body["error"]

    assert response.status_code == 500
    assert isinstance(error, dict)
    assert "internal_message" not in error
    assert "exception_type" not in error


def test_internal_response_includes_diagnostics() -> None:
    failure = mapper().map(
        RuntimeError("internal database detail")
    )

    response = ApplicationFailureResponse.from_failure(
        failure,
        include_internal=True,
    )

    error = response.body["error"]

    assert isinstance(error, dict)
    assert error["internal_message"] == (
        "internal database detail"
    )
    assert error["exception_type"] == "RuntimeError"
