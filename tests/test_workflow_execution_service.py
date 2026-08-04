"""Tests for the workflow execution application service."""

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
from app.application.workflow_execution import (
    ApplicationWorkflowExecutionOutput,
    ApplicationWorkflowExecutionRequest,
    ApplicationWorkflowStepResult,
    ApplicationWorkflowStepStatus,
)
from app.application.workflow_execution_service import (
    ApplicationWorkflowExecutionService,
)
from app.application.workflow_execution_service_error import (
    ApplicationWorkflowExecutionFailedError,
    ApplicationWorkflowExecutionServiceError,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    5,
    0,
    tzinfo=UTC,
)


class SuccessfulWorkflowRunner:
    """Return one deterministic successful workflow."""

    def __init__(self) -> None:
        self.requests: list[
            ApplicationWorkflowExecutionRequest
        ] = []

    def execute(
        self,
        request: ApplicationWorkflowExecutionRequest,
    ) -> ApplicationWorkflowExecutionOutput:
        """Execute one successful workflow."""

        self.requests.append(request)

        return ApplicationWorkflowExecutionOutput(
            summary="Research workflow completed.",
            result={
                "report_id": "report-001",
                "claim_count": 4,
            },
            steps=[
                ApplicationWorkflowStepResult(
                    step_id="step-search",
                    step_type="tool",
                    status=(
                        ApplicationWorkflowStepStatus.SUCCEEDED
                    ),
                    summary="Sources were retrieved.",
                    execution_id="tool-execution-001",
                    output={
                        "source_count": 5,
                    },
                ),
                ApplicationWorkflowStepResult(
                    step_id="step-report",
                    step_type="agent",
                    status=(
                        ApplicationWorkflowStepStatus.SUCCEEDED
                    ),
                    summary="The report was generated.",
                    execution_id="agent-execution-001",
                    output={
                        "report_id": "report-001",
                    },
                ),
            ],
            artifact_ids=["report-001"],
            metadata={
                "workflow_version": "1.0.0",
            },
        )


class RuntimeFailingWorkflowRunner:
    """Raise one controlled workflow failure."""

    def execute(
        self,
        request: ApplicationWorkflowExecutionRequest,
    ) -> ApplicationWorkflowExecutionOutput:
        """Raise a workflow runtime error."""

        del request

        raise RuntimeError(
            "The workflow coordinator is unavailable."
        )


class ValidationFailingWorkflowRunner:
    """Raise one workflow validation error."""

    def execute(
        self,
        request: ApplicationWorkflowExecutionRequest,
    ) -> ApplicationWorkflowExecutionOutput:
        """Raise an invalid workflow input error."""

        del request

        raise ValueError(
            "The workflow input is invalid."
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
) -> ApplicationWorkflowExecutionRequest:
    """Return one valid workflow request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "workflow_id": "research-workflow-001",
        "objective": "Produce a grounded research report.",
        "input_payload": {
            "query": "retrieval-grounded agents",
        },
        "actor_id": "user-001",
        "attempt_number": 1,
        "maximum_attempts": 3,
        "metadata": {
            "source": "test",
        },
    }
    values.update(overrides)

    return ApplicationWorkflowExecutionRequest.model_validate(
        values
    )


def service(
    *,
    runner: object,
) -> tuple[
    ApplicationWorkflowExecutionService,
    InMemoryApplicationExecutionRepository,
]:
    """Return one deterministic workflow service."""

    repository = InMemoryApplicationExecutionRepository()

    value = ApplicationWorkflowExecutionService(
        execution_repository=repository,
        runner=runner,
        clock=IncrementingClock(),
        execution_id_factory=lambda: "workflow-execution-001",
    )

    return value, repository


def test_successful_workflow_execution() -> None:
    runner = SuccessfulWorkflowRunner()
    value, repository = service(runner=runner)

    result = value.execute(request())

    assert result.execution.execution_id == (
        "workflow-execution-001"
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
        "Research workflow completed."
    )
    assert len(result.output.steps) == 2
    assert len(runner.requests) == 1
    assert repository.require(
        "workflow-execution-001"
    ) == result.execution


def test_existing_execution_hierarchy_is_preserved() -> None:
    value, _ = service(
        runner=SuccessfulWorkflowRunner()
    )

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
    value, _ = service(
        runner=SuccessfulWorkflowRunner()
    )

    result = value.execute(
        request(
            root_execution_id="workflow-execution-root",
            previous_attempt_execution_id=(
                "workflow-execution-previous"
            ),
            attempt_number=2,
            maximum_attempts=3,
        )
    )

    assert result.execution.attempt_number == 2
    assert (
        result.execution.previous_attempt_execution_id
        == "workflow-execution-previous"
    )


def test_runtime_failure_is_persisted() -> None:
    value, repository = service(
        runner=RuntimeFailingWorkflowRunner()
    )

    with pytest.raises(
        ApplicationWorkflowExecutionFailedError,
        match=(
            "RuntimeError: "
            "The workflow coordinator is unavailable"
        ),
    ):
        value.execute(request())

    failed = repository.require(
        "workflow-execution-001"
    )

    assert failed.status is (
        ApplicationExecutionStatus.FAILED
    )
    assert failed.record_version == 3
    assert failed.failure is not None
    assert failed.failure.category is (
        ApplicationExecutionFailureCategory.INTERNAL
    )


def test_validation_failure_is_persisted() -> None:
    value, repository = service(
        runner=ValidationFailingWorkflowRunner()
    )

    with pytest.raises(
        ApplicationWorkflowExecutionFailedError,
        match=(
            "ValueError: The workflow input is invalid"
        ),
    ):
        value.execute(request())

    failed = repository.require(
        "workflow-execution-001"
    )

    assert failed.failure is not None
    assert failed.failure.category is (
        ApplicationExecutionFailureCategory.VALIDATION
    )


def test_blank_execution_id_is_rejected() -> None:
    value = ApplicationWorkflowExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulWorkflowRunner(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: " ",
    )

    with pytest.raises(
        ApplicationWorkflowExecutionServiceError,
        match="execution ID factory returned blank value",
    ):
        value.execute(request())


def test_naive_clock_is_rejected() -> None:
    value = ApplicationWorkflowExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulWorkflowRunner(),
        clock=lambda: datetime(  # noqa: DTZ001
            2026,
            8,
            5,
            5,
            0,
        ),
        execution_id_factory=lambda: "workflow-execution-001",
    )

    with pytest.raises(
        ApplicationWorkflowExecutionServiceError,
        match=(
            "clock must return timezone-aware datetime"
        ),
    ):
        value.execute(request())


def test_request_rejects_blank_objective() -> None:
    with pytest.raises(
        ValidationError,
        match="objective must not be blank",
    ):
        request(objective=" ")


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


def test_output_rejects_duplicate_step_ids() -> None:
    step = ApplicationWorkflowStepResult(
        step_id="step-001",
        step_type="tool",
        status=ApplicationWorkflowStepStatus.SUCCEEDED,
        summary="Step completed.",
    )

    with pytest.raises(
        ValidationError,
        match="steps must have unique step IDs",
    ):
        ApplicationWorkflowExecutionOutput(
            summary="Workflow completed.",
            steps=[
                step,
                step.model_copy(
                    update={"step_id": "STEP-001"}
                ),
            ],
        )


def test_successful_output_rejects_failed_step() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "successful workflow output must not contain "
            "failed steps"
        ),
    ):
        ApplicationWorkflowExecutionOutput(
            summary="Workflow result.",
            steps=[
                ApplicationWorkflowStepResult(
                    step_id="step-failed",
                    step_type="agent",
                    status=(
                        ApplicationWorkflowStepStatus.FAILED
                    ),
                    summary="The step failed.",
                    error_code="AGENT_ERROR",
                    error_message="Agent execution failed.",
                )
            ],
        )


def test_failed_step_requires_error_details() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed workflow step requires error details"
        ),
    ):
        ApplicationWorkflowStepResult(
            step_id="step-failed",
            step_type="agent",
            status=ApplicationWorkflowStepStatus.FAILED,
            summary="The step failed.",
        )
