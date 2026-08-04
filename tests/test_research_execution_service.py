"""Tests for the research execution application service."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.execution_record import (
    ApplicationExecutionStatus,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)
from app.application.research_execution import (
    ApplicationResearchExecutionOutput,
    ApplicationResearchExecutionRequest,
)
from app.application.research_execution_service import (
    ApplicationResearchExecutionService,
)
from app.application.research_execution_service_error import (
    ApplicationResearchExecutionFailedError,
    ApplicationResearchExecutionServiceError,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    4,
    30,
    tzinfo=UTC,
)


class SuccessfulResearchRunner:
    """Deterministic successful research runner."""

    def __init__(self) -> None:
        self.requests: list[
            ApplicationResearchExecutionRequest
        ] = []

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Return one normalized research output."""

        self.requests.append(request)

        return ApplicationResearchExecutionOutput(
            summary="Research completed successfully.",
            result={
                "answer": "A grounded research answer.",
                "source_count": 3,
            },
            artifact_ids=["report-001"],
            citation_ids=[
                "citation-001",
                "citation-002",
            ],
        )


class FailingResearchRunner:
    """Deterministic failing research runner."""

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Raise a controlled runner failure."""

        del request

        raise RuntimeError(
            "The research provider is unavailable."
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
) -> ApplicationResearchExecutionRequest:
    """Return one valid research execution request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "agent_id": "research-agent-001",
        "query": "Explain retrieval-grounded agents.",
        "attempt_number": 1,
        "maximum_attempts": 3,
        "context": {
            "language": "en",
        },
        "metadata": {
            "source": "test",
        },
    }
    values.update(overrides)

    return ApplicationResearchExecutionRequest.model_validate(
        values
    )


def test_successful_research_execution() -> None:
    repository = InMemoryApplicationExecutionRepository()
    runner = SuccessfulResearchRunner()

    service = ApplicationResearchExecutionService(
        execution_repository=repository,
        runner=runner,
        clock=IncrementingClock(),
        execution_id_factory=lambda: "execution-001",
    )

    result = service.execute(request())

    assert result.execution.execution_id == "execution-001"
    assert result.execution.root_execution_id == (
        "execution-001"
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
        "Research completed successfully."
    )
    assert len(runner.requests) == 1

    stored = repository.require("execution-001")

    assert stored == result.execution
    assert stored.terminal is True


def test_existing_root_execution_is_preserved() -> None:
    repository = InMemoryApplicationExecutionRepository()

    service = ApplicationResearchExecutionService(
        execution_repository=repository,
        runner=SuccessfulResearchRunner(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: "execution-child",
    )

    result = service.execute(
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
    repository = InMemoryApplicationExecutionRepository()

    service = ApplicationResearchExecutionService(
        execution_repository=repository,
        runner=SuccessfulResearchRunner(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: "execution-002",
    )

    result = service.execute(
        request(
            root_execution_id="execution-001",
            previous_attempt_execution_id=(
                "execution-001"
            ),
            attempt_number=2,
            maximum_attempts=3,
        )
    )

    assert result.execution.attempt_number == 2
    assert (
        result.execution.previous_attempt_execution_id
        == "execution-001"
    )


def test_runner_failure_is_persisted() -> None:
    repository = InMemoryApplicationExecutionRepository()

    service = ApplicationResearchExecutionService(
        execution_repository=repository,
        runner=FailingResearchRunner(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: "execution-failed",
    )

    with pytest.raises(
        ApplicationResearchExecutionFailedError,
        match=(
            "research execution failed: execution-failed: "
            "The research provider is unavailable"
        ),
    ) as captured:
        service.execute(request())

    assert captured.value.execution_id == (
        "execution-failed"
    )

    failed = repository.require("execution-failed")

    assert failed.status is (
        ApplicationExecutionStatus.FAILED
    )
    assert failed.record_version == 3
    assert failed.failure is not None
    assert failed.failure.code == "RuntimeError"
    assert failed.failure.retryable is False
    assert failed.finished_at == (
        BASE_TIME + timedelta(seconds=2)
    )


def test_blank_execution_id_is_rejected() -> None:
    service = ApplicationResearchExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulResearchRunner(),
        clock=IncrementingClock(),
        execution_id_factory=lambda: " ",
    )

    with pytest.raises(
        ApplicationResearchExecutionServiceError,
        match="execution ID factory returned blank value",
    ):
        service.execute(request())


def test_naive_clock_is_rejected() -> None:
    service = ApplicationResearchExecutionService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        runner=SuccessfulResearchRunner(),
        clock=lambda: datetime(  # noqa: DTZ001
            2026,
            8,
            5,
            4,
            30,
        ),
        execution_id_factory=lambda: "execution-001",
    )

    with pytest.raises(
        ApplicationResearchExecutionServiceError,
        match=(
            "clock must return timezone-aware datetime"
        ),
    ):
        service.execute(request())


def test_request_rejects_blank_query() -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        request(query=" ")


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


def test_output_rejects_duplicate_citations() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation_ids must not contain duplicates"
        ),
    ):
        ApplicationResearchExecutionOutput(
            summary="Research output.",
            citation_ids=[
                "CITATION-001",
                "citation-001",
            ],
        )
