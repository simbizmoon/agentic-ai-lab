"""Phase 12 end-to-end application flow tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from app.application.failure import (
    ApplicationFailureCategory,
)
from app.application.failure_mapper import (
    ApplicationFailureMapper,
)
from app.application.idempotency_record import (
    ApplicationIdempotencyRecord,
    ApplicationIdempotencyStatus,
)
from app.application.idempotency_service import (
    ApplicationIdempotencyService,
)
from app.application.idempotency_service_error import (
    ApplicationIdempotencyConflictError,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)
from app.application.in_memory_idempotency_repository import (
    InMemoryApplicationIdempotencyRepository,
)
from app.application.in_memory_transaction_manager import (
    InMemoryApplicationTransactionManager,
)
from app.application.research_application_flow import (
    ApplicationResearchFlowRequest,
)
from app.application.research_application_flow_error import (
    ApplicationResearchFlowStateError,
)
from app.application.research_application_flow_service import (
    ApplicationResearchFlowService,
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
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    5,
    50,
    tzinfo=UTC,
)


class IncrementingClock:
    """Return deterministic increasing timestamps."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> datetime:
        value = BASE_TIME + timedelta(
            seconds=self._calls
        )
        self._calls += 1
        return value


class SequenceIdFactory:
    """Return deterministic identifiers in sequence."""

    def __init__(
        self,
        *values: str,
    ) -> None:
        self._values = iter(values)

    def __call__(self) -> str:
        return next(self._values)


class SuccessfulResearchRunner:
    """Return deterministic successful research output."""

    def __init__(self) -> None:
        self.call_count = 0

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Execute one successful research request."""

        self.call_count += 1

        return ApplicationResearchExecutionOutput(
            summary="Grounded research completed.",
            result={
                "query": request.query,
                "claim_count": 3,
            },
            artifact_ids=["report-001"],
            citation_ids=[
                "citation-001",
                "citation-002",
            ],
        )


class FailingResearchRunner:
    """Raise a deterministic research execution failure."""

    def __init__(self) -> None:
        self.call_count = 0

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Fail one research request."""

        del request
        self.call_count += 1

        raise RuntimeError(
            "Research provider unavailable."
        )


def research_request(
    *,
    query: str = "Explain grounded research agents.",
) -> ApplicationResearchExecutionRequest:
    """Return one valid research execution request."""

    return ApplicationResearchExecutionRequest(
        request_id="research-request-001",
        workspace_id="workspace-001",
        agent_id="research-agent-001",
        query=query,
        attempt_number=1,
        maximum_attempts=3,
        context={
            "language": "en",
        },
        metadata={
            "source": "phase12-e2e",
        },
    )


def flow_request(
    *,
    query: str = "Explain grounded research agents.",
) -> ApplicationResearchFlowRequest:
    """Return one valid application flow request."""

    return ApplicationResearchFlowRequest(
        idempotency_key="research-key-001",
        research=research_request(query=query),
        metadata={
            "channel": "test",
        },
    )


def build_flow(
    *,
    runner: object,
    execution_id_factory: Callable[[], str] | None = None,
) -> tuple[
    ApplicationResearchFlowService,
    InMemoryApplicationExecutionRepository,
    InMemoryApplicationIdempotencyRepository,
]:
    """Build complete Phase 12 in-memory infrastructure."""

    execution_repository = (
        InMemoryApplicationExecutionRepository()
    )
    idempotency_repository = (
        InMemoryApplicationIdempotencyRepository()
    )
    clock = IncrementingClock()

    idempotency_service = ApplicationIdempotencyService(
        repository=idempotency_repository,
        clock=clock,
        record_id_factory=lambda: "idempotency-001",
    )

    research_service = ApplicationResearchExecutionService(
        execution_repository=execution_repository,
        runner=runner,
        clock=clock,
        execution_id_factory=(
            execution_id_factory
            or (lambda: "execution-001")
        ),
    )

    transaction_manager = (
        InMemoryApplicationTransactionManager(
            resources=[
                execution_repository,
                idempotency_repository,
            ]
        )
    )

    flow = ApplicationResearchFlowService(
        transaction_manager=transaction_manager,
        idempotency_service=idempotency_service,
        research_execution_service=research_service,
        execution_repository=execution_repository,
    )

    return (
        flow,
        execution_repository,
        idempotency_repository,
    )


def get_idempotency_record(
    repository: InMemoryApplicationIdempotencyRepository,
) -> ApplicationIdempotencyRecord:
    """Return the test flow's idempotency record."""

    record = repository.find(
        workspace_id="workspace-001",
        operation="research.execute",
        idempotency_key="research-key-001",
    )

    if record is None:
        raise AssertionError(
            "expected idempotency record was not found"
        )

    return record


def test_successful_e2e_flow_persists_all_state() -> None:
    runner = SuccessfulResearchRunner()
    flow, executions, idempotency = build_flow(
        runner=runner
    )

    result = flow.execute(flow_request())

    assert result.reused is False
    assert result.idempotency_record_id == (
        "idempotency-001"
    )
    assert result.research_result.execution.execution_id == (
        "execution-001"
    )
    assert result.research_result.execution.terminal is True
    assert result.research_result.output.summary == (
        "Grounded research completed."
    )
    assert runner.call_count == 1

    stored_execution = executions.require(
        "execution-001"
    )
    stored_idempotency = get_idempotency_record(
        idempotency
    )

    assert stored_execution == (
        result.research_result.execution
    )
    assert stored_idempotency.status is (
        ApplicationIdempotencyStatus.SUCCEEDED
    )
    assert stored_idempotency.result is not None


def test_duplicate_success_reuses_previous_result() -> None:
    runner = SuccessfulResearchRunner()
    flow, _, idempotency = build_flow(
        runner=runner
    )

    first = flow.execute(flow_request())
    second = flow.execute(flow_request())

    assert first.reused is False
    assert second.reused is True
    assert runner.call_count == 1
    assert (
        second.research_result.execution.execution_id
        == first.research_result.execution.execution_id
    )
    assert (
        second.research_result.output
        == first.research_result.output
    )
    assert get_idempotency_record(
        idempotency
    ).record_version == 2


def test_different_payload_with_same_key_is_rejected() -> None:
    runner = SuccessfulResearchRunner()
    flow, _, _ = build_flow(runner=runner)

    flow.execute(flow_request())

    with pytest.raises(
        ApplicationIdempotencyConflictError,
        match="different request payload",
    ):
        flow.execute(
            flow_request(
                query="A different research question."
            )
        )

    assert runner.call_count == 1


def test_execution_failure_persists_both_failures() -> None:
    runner = FailingResearchRunner()
    flow, executions, idempotency = build_flow(
        runner=runner
    )

    with pytest.raises(
        ApplicationResearchExecutionFailedError,
        match="Research provider unavailable",
    ):
        flow.execute(flow_request())

    failed_execution = executions.require(
        "execution-001"
    )
    failed_idempotency = get_idempotency_record(
        idempotency
    )

    assert failed_execution.terminal is True
    assert failed_execution.failure is not None
    assert failed_idempotency.status is (
        ApplicationIdempotencyStatus.FAILED
    )
    assert failed_idempotency.failure is not None
    assert failed_idempotency.failure.message == (
        "Research provider unavailable."
    )
    assert runner.call_count == 1


def test_execution_failure_maps_to_standard_failure() -> None:
    runner = FailingResearchRunner()
    flow, _, _ = build_flow(runner=runner)

    with pytest.raises(
        ApplicationResearchExecutionFailedError
    ) as captured:
        flow.execute(flow_request())

    failure = ApplicationFailureMapper().map(
        captured.value
    )

    assert failure.category is (
        ApplicationFailureCategory.EXECUTION
    )
    assert failure.code == "RESEARCH_EXECUTION_FAILED"
    assert failure.execution_id == "execution-001"
    assert failure.status_code == 500


def test_invalid_reused_execution_reference_is_rejected() -> None:
    runner = SuccessfulResearchRunner()
    flow, executions, _ = build_flow(
        runner=runner
    )

    flow.execute(flow_request())
    executions.clear()

    with pytest.raises(
        ApplicationResearchFlowStateError,
        match=(
            "stored idempotency execution was not found"
        ),
    ):
        flow.execute(flow_request())

    assert runner.call_count == 1


def test_failed_flow_can_retry_with_new_execution() -> None:
    class RecoveringResearchRunner:
        """Fail once and then return a successful result."""

        def __init__(self) -> None:
            self.call_count = 0

        def execute(
            self,
            request: ApplicationResearchExecutionRequest,
        ) -> ApplicationResearchExecutionOutput:
            self.call_count += 1

            if self.call_count == 1:
                raise RuntimeError(
                    "Temporary research failure."
                )

            return ApplicationResearchExecutionOutput(
                summary="Research recovered.",
                result={
                    "query": request.query,
                },
            )

    runner = RecoveringResearchRunner()
    execution_ids = SequenceIdFactory(
        "execution-001",
        "execution-002",
    )

    flow, executions, idempotency = build_flow(
        runner=runner,
        execution_id_factory=execution_ids,
    )

    with pytest.raises(
        ApplicationResearchExecutionFailedError
    ):
        flow.execute(flow_request())

    recovered = flow.execute(flow_request())

    assert recovered.reused is False
    assert (
        recovered.research_result.execution.execution_id
        == "execution-002"
    )
    assert runner.call_count == 2
    assert executions.exists("execution-001") is True
    assert executions.exists("execution-002") is True

    stored_idempotency = get_idempotency_record(
        idempotency
    )

    assert stored_idempotency.status is (
        ApplicationIdempotencyStatus.SUCCEEDED
    )
    assert stored_idempotency.record_version == 4
