"""Tests for the tool execution application service."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.execution_record import (
    ApplicationExecutionFailureCategory,
    ApplicationExecutionStatus,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)
from app.application.tool_execution import (
    ApplicationToolExecutionOutput,
    ApplicationToolExecutionRequest,
)
from app.application.tool_execution_service import (
    ApplicationToolExecutionService,
)
from app.application.tool_execution_service_error import (
    ApplicationToolExecutionFailedError,
    ApplicationToolExecutionServiceError,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    4,
    40,
    tzinfo=UTC,
)


class AllowAllToolPermissionChecker:
    """Allow every tool execution."""

    def require_allowed(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> None:
        """Allow the tool request."""

        del request


class DenyToolPermissionChecker:
    """Deny every tool execution."""

    def require_allowed(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> None:
        """Reject the tool request."""

        raise PermissionError(
            f"Tool is not permitted: {request.tool_id}"
        )


class SuccessfulToolRunner:
    """Return one deterministic tool result."""

    def __init__(self) -> None:
        self.requests: list[
            ApplicationToolExecutionRequest
        ] = []

    def execute(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> ApplicationToolExecutionOutput:
        """Execute one successful tool call."""

        self.requests.append(request)

        return ApplicationToolExecutionOutput(
            result={
                "documents": [
                    {
                        "document_id": "document-001",
                        "title": "Grounded Agents",
                    }
                ]
            },
            summary="One document was found.",
            artifact_ids=["artifact-001"],
            metadata={
                "provider": "test-search",
            },
        )


class RuntimeFailingToolRunner:
    """Raise one controlled tool execution error."""

    def execute(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> ApplicationToolExecutionOutput:
        """Raise a runtime tool failure."""

        del request

        raise RuntimeError(
            "The tool provider is unavailable."
        )


class ValidationFailingToolRunner:
    """Raise one tool argument validation error."""

    def execute(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> ApplicationToolExecutionOutput:
        """Raise an argument validation error."""

        del request

        raise ValueError(
            "The query argument is invalid."
        )


class IncrementingClock:
    """Return increasing timezone-aware timestamps."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> datetime:
        value = BASE_TIME + timedelta(
            seconds=self._calls
        )
        self._calls += 1
        return value


def request(
    **overrides: object,
) -> ApplicationToolExecutionRequest:
    """Return one valid tool execution request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "tool_id": "source-search",
        "operation": "search",
        "arguments": {
            "query": "retrieval-grounded agents",
            "limit": 5,
        },
        "actor_id": "research-agent-001",
        "assignment_id": "assignment-001",
        "attempt_number": 1,
        "maximum_attempts": 3,
        "metadata": {
            "source": "test",
        },
    }
    values.update(overrides)

    return ApplicationToolExecutionRequest.model_validate(
        values
    )


def service(
    *,
    runner: object,
    permission_checker: object | None = None,
    repository: InMemoryApplicationExecutionRepository
    | None = None,
) -> tuple[
    ApplicationToolExecutionService,
    InMemoryApplicationExecutionRepository,
]:
    """Return one deterministic tool service."""

    execution_repository = (
        repository
        or InMemoryApplicationExecutionRepository()
    )

    value = ApplicationToolExecutionService(
        execution_repository=execution_repository,
        runner=runner,
        permission_checker=(
            permission_checker
            or AllowAllToolPermissionChecker()
        ),
        clock=IncrementingClock(),
        execution_id_factory=lambda: "tool-execution-001",
    )

    return value, execution_repository


def test_successful_tool_execution() -> None:
    runner = SuccessfulToolRunner()
    value, repository = service(runner=runner)

    result = value.execute(request())

    assert result.execution.execution_id == (
        "tool-execution-001"
    )
    assert result.execution.status is (
        ApplicationExecutionStatus.SUCCEEDED
    )
    assert result.execution.record_version == 3
    assert result.execution.started_at == (
        BASE_TIME + timedelta(seconds=1)
    )
    assert result.execution.finished_at == (
        BASE_TIME + timedelta(seconds=2)
    )
    assert result.output.summary == (
        "One document was found."
    )
    assert len(runner.requests) == 1
    assert repository.require(
        "tool-execution-001"
    ) == result.execution


def test_permission_denial_is_persisted() -> None:
    runner = SuccessfulToolRunner()
    value, repository = service(
        runner=runner,
        permission_checker=DenyToolPermissionChecker(),
    )

    with pytest.raises(
        ApplicationToolExecutionFailedError,
        match=(
            "tool execution failed: tool-execution-001: "
            "PermissionError: Tool is not permitted"
        ),
    ):
        value.execute(request())

    failed = repository.require("tool-execution-001")

    assert failed.status is (
        ApplicationExecutionStatus.FAILED
    )
    assert failed.failure is not None
    assert failed.failure.category is (
        ApplicationExecutionFailureCategory.PERMISSION
    )
    assert failed.failure.code == "PermissionError"
    assert runner.requests == []


def test_runtime_failure_is_persisted() -> None:
    value, repository = service(
        runner=RuntimeFailingToolRunner()
    )

    with pytest.raises(
        ApplicationToolExecutionFailedError,
        match=(
            "RuntimeError: The tool provider is unavailable"
        ),
    ):
        value.execute(request())

    failed = repository.require("tool-execution-001")

    assert failed.failure is not None
    assert failed.failure.category is (
        ApplicationExecutionFailureCategory.TOOL
    )
    assert failed.record_version == 3


def test_validation_failure_is_persisted() -> None:
    value, repository = service(
        runner=ValidationFailingToolRunner()
    )

    with pytest.raises(
        ApplicationToolExecutionFailedError,
        match=(
            "ValueError: The query argument is invalid"
        ),
    ):
        value.execute(request())

    failed = repository.require("tool-execution-001")

    assert failed.failure is not None
    assert failed.failure.category is (
        ApplicationExecutionFailureCategory.VALIDATION
    )


def test_existing_execution_hierarchy_is_preserved() -> None:
    value, _ = service(runner=SuccessfulToolRunner())

    result = value.execute(
        request(
            root_execution_id="execution-root",
            parent_execution_id="execution-parent",
        )
    )

    assert result.execution.root_execution_id == (
        "execution-root"
    )
    assert result.execution.parent_execution_id == (
        "execution-parent"
    )


def test_retry_execution_links_previous_attempt() -> None:
    value, _ = service(runner=SuccessfulToolRunner())

    result = value.execute(
        request(
            root_execution_id="tool-execution-root",
            previous_attempt_execution_id=(
                "tool-execution-previous"
            ),
            attempt_number=2,
            maximum_attempts=3,
        )
    )

    assert result.execution.attempt_number == 2
    assert (
        result.execution.previous_attempt_execution_id
        == "tool-execution-previous"
    )


def test_blank_execution_id_is_rejected() -> None:
    value = ApplicationToolExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulToolRunner(),
        permission_checker=AllowAllToolPermissionChecker(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: " ",
    )

    with pytest.raises(
        ApplicationToolExecutionServiceError,
        match="execution ID factory returned blank value",
    ):
        value.execute(request())


def test_naive_clock_is_rejected() -> None:
    value = ApplicationToolExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulToolRunner(),
        permission_checker=AllowAllToolPermissionChecker(),
        clock=lambda: datetime(  # noqa: DTZ001
            2026,
            8,
            5,
            4,
            40,
        ),
        execution_id_factory=lambda: "tool-execution-001",
    )

    with pytest.raises(
        ApplicationToolExecutionServiceError,
        match=(
            "clock must return timezone-aware datetime"
        ),
    ):
        value.execute(request())


def test_request_rejects_blank_operation() -> None:
    with pytest.raises(
        ValidationError,
        match="operation must not be blank",
    ):
        request(operation=" ")


def test_retry_request_requires_previous_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry attempt requires "
            "previous_attempt_execution_id"
        ),
    ):
        request(
            attempt_number=2,
            maximum_attempts=3,
        )


def test_output_rejects_duplicate_artifacts() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "artifact_ids must not contain duplicates"
        ),
    ):
        ApplicationToolExecutionOutput(
            result={"status": "ok"},
            summary="Tool completed.",
            artifact_ids=[
                "ARTIFACT-001",
                "artifact-001",
            ],
        )
