"""Tests for the application reliability query service."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.evaluation_record import (
    ApplicationEvaluationRecord,
    ApplicationEvaluationStatus,
    ApplicationEvaluationType,
    ApplicationEvaluationViolation,
)
from app.application.execution_record import (
    ApplicationExecutionFailure,
    ApplicationExecutionFailureCategory,
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.guardrail_record import (
    ApplicationGuardrailDecision,
    ApplicationGuardrailRecord,
    ApplicationGuardrailScope,
    ApplicationGuardrailSeverity,
    ApplicationGuardrailViolationRecord,
)
from app.application.in_memory_evaluation_repository import (
    InMemoryApplicationEvaluationRepository,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)
from app.application.in_memory_guardrail_repository import (
    InMemoryApplicationGuardrailRepository,
)
from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.job_record import (
    ApplicationJobFailure,
    ApplicationJobFailureCategory,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.reliability_query import (
    ApplicationReliabilityQuery,
)
from app.application.reliability_query_service import (
    ApplicationReliabilityQueryService,
)
from app.application.reliability_query_service_error import (
    ApplicationReliabilityQueryServiceError,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    5,
    10,
    tzinfo=UTC,
)


def execution_failure() -> ApplicationExecutionFailure:
    """Return one execution failure."""

    return ApplicationExecutionFailure(
        category=ApplicationExecutionFailureCategory.INTERNAL,
        code="EXECUTION_ERROR",
        message="Execution failed.",
        retryable=False,
    )


def execution(
    *,
    execution_id: str,
    status: ApplicationExecutionStatus,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    attempt_number: int = 1,
) -> ApplicationExecutionRecord:
    """Return one application execution record."""

    values: dict[str, object] = {
        "execution_id": execution_id,
        "root_execution_id": "execution-root",
        "previous_attempt_execution_id": (
            "execution-previous"
            if attempt_number > 1
            else None
        ),
        "request_id": request_id,
        "workspace_id": workspace_id,
        "subject_type": (
            ApplicationExecutionSubjectType.AGENT
        ),
        "subject_id": "agent-001",
        "status": status,
        "attempt_number": attempt_number,
        "maximum_attempts": 3,
        "created_at": BASE_TIME,
    }

    if status is ApplicationExecutionStatus.RUNNING:
        values["started_at"] = BASE_TIME

    if status in {
        ApplicationExecutionStatus.SUCCEEDED,
        ApplicationExecutionStatus.FAILED,
        ApplicationExecutionStatus.TIMED_OUT,
    }:
        values["started_at"] = BASE_TIME
        values["finished_at"] = (
            BASE_TIME + timedelta(seconds=1)
        )

    if status in {
        ApplicationExecutionStatus.FAILED,
        ApplicationExecutionStatus.TIMED_OUT,
    }:
        values["failure"] = execution_failure()

    return ApplicationExecutionRecord.model_validate(values)


def evaluation_violation() -> ApplicationEvaluationViolation:
    """Return one blocking evaluation violation."""

    return ApplicationEvaluationViolation(
        violation_id="evaluation-violation-001",
        code="MISSING_SUPPORT",
        message="Evidence support is missing.",
        blocking=True,
    )


def evaluation(
    *,
    evaluation_id: str,
    status: ApplicationEvaluationStatus,
    score: float | None,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    blocking: bool = False,
) -> ApplicationEvaluationRecord:
    """Return one application evaluation record."""

    return ApplicationEvaluationRecord(
        evaluation_id=evaluation_id,
        evaluation_type=(
            ApplicationEvaluationType.CLAIM_SUPPORT
        ),
        evaluator_name="claim-support-evaluator",
        evaluator_version="1.0.0",
        request_id=request_id,
        workspace_id=workspace_id,
        status=status,
        overall_score=score,
        threshold_score=(
            0.7 if score is not None else None
        ),
        violations=(
            [evaluation_violation()]
            if blocking
            else []
        ),
        started_at=BASE_TIME,
        finished_at=BASE_TIME + timedelta(seconds=1),
        summary="Evaluation completed.",
    )


def guardrail_violation(
    *,
    blocking: bool,
) -> ApplicationGuardrailViolationRecord:
    """Return one normalized guardrail violation."""

    return ApplicationGuardrailViolationRecord(
        violation_id=(
            "blocking-violation"
            if blocking
            else "warning-violation"
        ),
        policy_id="policy-001",
        code="POLICY_VIOLATION",
        message="A policy violation occurred.",
        severity=(
            ApplicationGuardrailSeverity.HIGH
            if blocking
            else ApplicationGuardrailSeverity.MEDIUM
        ),
        blocking=blocking,
    )


def guardrail(
    *,
    guardrail_id: str,
    decision: ApplicationGuardrailDecision,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
) -> ApplicationGuardrailRecord:
    """Return one application guardrail record."""

    violations: list[
        ApplicationGuardrailViolationRecord
    ] = []

    if decision is ApplicationGuardrailDecision.WARNED:
        violations = [
            guardrail_violation(blocking=False)
        ]

    if decision is ApplicationGuardrailDecision.BLOCKED:
        violations = [
            guardrail_violation(blocking=True)
        ]

    return ApplicationGuardrailRecord(
        guardrail_evaluation_id=guardrail_id,
        scope=ApplicationGuardrailScope.TOOL,
        evaluator_name="tool-guardrail",
        evaluator_version="1.0.0",
        request_id=request_id,
        workspace_id=workspace_id,
        target_id="tool-001",
        target_type="tool_call",
        decision=decision,
        violations=violations,
        total_violation_count=len(violations),
        blocking_violation_count=sum(
            item.blocking
            for item in violations
        ),
        warning_violation_count=sum(
            not item.blocking
            for item in violations
        ),
        evaluated_at=BASE_TIME,
        summary="Guardrail completed.",
    )


def job_failure() -> ApplicationJobFailure:
    """Return one persistent job failure."""

    return ApplicationJobFailure(
        category=ApplicationJobFailureCategory.EXECUTION,
        code="JOB_ERROR",
        message="Job failed.",
        retryable=False,
    )


def job(
    *,
    job_id: str,
    status: ApplicationJobStatus,
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    attempt_number: int = 1,
) -> ApplicationJobRecord:
    """Return one application job."""

    values: dict[str, object] = {
        "job_id": job_id,
        "root_job_id": "job-root",
        "previous_attempt_job_id": (
            "job-previous"
            if attempt_number > 1
            else None
        ),
        "request_id": request_id,
        "workspace_id": workspace_id,
        "job_type": ApplicationJobType.AGENT_EXECUTION,
        "queue_name": "research",
        "status": status,
        "attempt_number": attempt_number,
        "maximum_attempts": 3,
        "available_at": BASE_TIME,
        "created_at": BASE_TIME,
    }

    if status in {
        ApplicationJobStatus.SUCCEEDED,
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.DEAD_LETTERED,
    }:
        values["queued_at"] = BASE_TIME
        values["started_at"] = BASE_TIME
        values["finished_at"] = (
            BASE_TIME + timedelta(seconds=1)
        )

    if status in {
        ApplicationJobStatus.FAILED,
        ApplicationJobStatus.DEAD_LETTERED,
    }:
        values["failure"] = job_failure()

    return ApplicationJobRecord.model_validate(values)


def populated_service(
) -> ApplicationReliabilityQueryService:
    """Return a reliability service with mixed records."""

    return ApplicationReliabilityQueryService(
        execution_repository=(
            InMemoryApplicationExecutionRepository(
                [
                    execution(
                        execution_id="execution-001",
                        status=(
                            ApplicationExecutionStatus.SUCCEEDED
                        ),
                    ),
                    execution(
                        execution_id="execution-002",
                        status=(
                            ApplicationExecutionStatus.FAILED
                        ),
                        attempt_number=2,
                    ),
                    execution(
                        execution_id="execution-other",
                        status=(
                            ApplicationExecutionStatus.SUCCEEDED
                        ),
                        request_id="research-other",
                    ),
                ]
            )
        ),
        evaluation_repository=(
            InMemoryApplicationEvaluationRepository(
                [
                    evaluation(
                        evaluation_id="evaluation-001",
                        status=(
                            ApplicationEvaluationStatus.PASSED
                        ),
                        score=0.9,
                    ),
                    evaluation(
                        evaluation_id="evaluation-002",
                        status=(
                            ApplicationEvaluationStatus.FAILED
                        ),
                        score=0.5,
                        blocking=True,
                    ),
                    evaluation(
                        evaluation_id="evaluation-other",
                        status=(
                            ApplicationEvaluationStatus.PASSED
                        ),
                        score=1.0,
                        request_id="research-other",
                    ),
                ]
            )
        ),
        guardrail_repository=(
            InMemoryApplicationGuardrailRepository(
                [
                    guardrail(
                        guardrail_id="guardrail-001",
                        decision=(
                            ApplicationGuardrailDecision.ALLOWED
                        ),
                    ),
                    guardrail(
                        guardrail_id="guardrail-002",
                        decision=(
                            ApplicationGuardrailDecision.WARNED
                        ),
                    ),
                    guardrail(
                        guardrail_id="guardrail-003",
                        decision=(
                            ApplicationGuardrailDecision.BLOCKED
                        ),
                    ),
                ]
            )
        ),
        job_repository=InMemoryApplicationJobRepository(
            [
                job(
                    job_id="job-001",
                    status=ApplicationJobStatus.SUCCEEDED,
                ),
                job(
                    job_id="job-002",
                    status=ApplicationJobStatus.FAILED,
                    attempt_number=2,
                ),
                job(
                    job_id="job-003",
                    status=ApplicationJobStatus.PENDING,
                ),
            ]
        ),
        clock=lambda: BASE_TIME,
        snapshot_id_factory=lambda: "snapshot-001",
    )


def test_query_aggregates_reliability_metrics() -> None:
    service = populated_service()

    snapshot = service.query(
        ApplicationReliabilityQuery(
            request_id="research-001",
            workspace_id="workspace-001",
        )
    )

    assert snapshot.snapshot_id == "snapshot-001"
    assert snapshot.generated_at == BASE_TIME

    assert snapshot.executions.total == 2
    assert snapshot.executions.succeeded == 1
    assert snapshot.executions.failed == 1
    assert snapshot.executions.retry_attempts == 1
    assert snapshot.executions.success_rate == (
        pytest.approx(0.5)
    )
    assert snapshot.executions.retry_rate == (
        pytest.approx(0.5)
    )

    assert snapshot.evaluations.total == 2
    assert snapshot.evaluations.passed == 1
    assert snapshot.evaluations.failed == 1
    assert snapshot.evaluations.blocking_results == 1
    assert snapshot.evaluations.average_score == (
        pytest.approx(0.7)
    )

    assert snapshot.guardrails.total == 3
    assert snapshot.guardrails.allowed == 1
    assert snapshot.guardrails.warned == 1
    assert snapshot.guardrails.blocked == 1
    assert snapshot.guardrails.total_violations == 2
    assert snapshot.guardrails.blocking_violations == 1
    assert snapshot.guardrails.warning_violations == 1

    assert snapshot.jobs.total == 3
    assert snapshot.jobs.succeeded == 1
    assert snapshot.jobs.failed == 1
    assert snapshot.jobs.pending == 1
    assert snapshot.jobs.retry_attempts == 1
    assert snapshot.jobs.completion_rate == (
        pytest.approx(2 / 3)
    )


def test_empty_repositories_return_zero_rates() -> None:
    service = ApplicationReliabilityQueryService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        evaluation_repository=(
            InMemoryApplicationEvaluationRepository()
        ),
        guardrail_repository=(
            InMemoryApplicationGuardrailRepository()
        ),
        job_repository=InMemoryApplicationJobRepository(),
        clock=lambda: BASE_TIME,
        snapshot_id_factory=lambda: "snapshot-empty",
    )

    snapshot = service.query(
        ApplicationReliabilityQuery()
    )

    assert snapshot.executions.total == 0
    assert snapshot.executions.success_rate == 0.0
    assert snapshot.evaluations.average_score is None
    assert snapshot.guardrails.blocking_rate == 0.0
    assert snapshot.jobs.completion_rate == 0.0


def test_workspace_filter_is_applied() -> None:
    service = populated_service()

    snapshot = service.query(
        ApplicationReliabilityQuery(
            workspace_id="workspace-001"
        )
    )

    assert snapshot.executions.total == 3
    assert snapshot.evaluations.total == 3
    assert snapshot.guardrails.total == 3
    assert snapshot.jobs.total == 3


def test_blank_snapshot_id_is_rejected() -> None:
    service = ApplicationReliabilityQueryService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        evaluation_repository=(
            InMemoryApplicationEvaluationRepository()
        ),
        guardrail_repository=(
            InMemoryApplicationGuardrailRepository()
        ),
        job_repository=InMemoryApplicationJobRepository(),
        clock=lambda: BASE_TIME,
        snapshot_id_factory=lambda: " ",
    )

    with pytest.raises(
        ApplicationReliabilityQueryServiceError,
        match="snapshot ID factory returned blank value",
    ):
        service.query(ApplicationReliabilityQuery())


def test_naive_clock_is_rejected() -> None:
    service = ApplicationReliabilityQueryService(
        execution_repository=(
            InMemoryApplicationExecutionRepository()
        ),
        evaluation_repository=(
            InMemoryApplicationEvaluationRepository()
        ),
        guardrail_repository=(
            InMemoryApplicationGuardrailRepository()
        ),
        job_repository=InMemoryApplicationJobRepository(),
        clock=lambda: datetime(  # noqa: DTZ001
            2026,
            8,
            5,
            5,
            10,
        ),
        snapshot_id_factory=lambda: "snapshot-001",
    )

    with pytest.raises(
        ApplicationReliabilityQueryServiceError,
        match=(
            "clock must return timezone-aware datetime"
        ),
    ):
        service.query(ApplicationReliabilityQuery())


def test_query_rejects_blank_request_id() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "request_id must not be blank when provided"
        ),
    ):
        ApplicationReliabilityQuery(request_id=" ")
