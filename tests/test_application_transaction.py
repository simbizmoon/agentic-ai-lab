"""Tests for the in-memory application transaction boundary."""

from datetime import UTC, datetime

import pytest

from app.application.evaluation_record import (
    ApplicationEvaluationRecord,
    ApplicationEvaluationStatus,
    ApplicationEvaluationType,
)
from app.application.execution_record import (
    ApplicationExecutionRecord,
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)
from app.application.in_memory_evaluation_repository import (
    InMemoryApplicationEvaluationRepository,
)
from app.application.in_memory_execution_repository import (
    InMemoryApplicationExecutionRepository,
)
from app.application.in_memory_job_repository import (
    InMemoryApplicationJobRepository,
)
from app.application.in_memory_transaction_manager import (
    InMemoryApplicationTransactionManager,
)
from app.application.job_record import (
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.transaction_error import (
    ApplicationNestedTransactionError,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    5,
    20,
    tzinfo=UTC,
)


def execution(
    execution_id: str,
) -> ApplicationExecutionRecord:
    """Return one pending execution."""

    return ApplicationExecutionRecord(
        execution_id=execution_id,
        root_execution_id=execution_id,
        request_id="research-001",
        workspace_id="workspace-001",
        subject_type=ApplicationExecutionSubjectType.AGENT,
        subject_id="agent-001",
        status=ApplicationExecutionStatus.PENDING,
        created_at=BASE_TIME,
    )


def evaluation(
    evaluation_id: str,
) -> ApplicationEvaluationRecord:
    """Return one successful evaluation record."""

    return ApplicationEvaluationRecord(
        evaluation_id=evaluation_id,
        evaluation_type=(
            ApplicationEvaluationType.CLAIM_SUPPORT
        ),
        evaluator_name="claim-support-evaluator",
        evaluator_version="1.0.0",
        request_id="research-001",
        workspace_id="workspace-001",
        status=ApplicationEvaluationStatus.PASSED,
        overall_score=0.9,
        threshold_score=0.7,
        started_at=BASE_TIME,
        finished_at=BASE_TIME,
        summary="Evaluation passed.",
    )


def job(
    job_id: str,
) -> ApplicationJobRecord:
    """Return one pending background job."""

    return ApplicationJobRecord(
        job_id=job_id,
        root_job_id=job_id,
        request_id="research-001",
        workspace_id="workspace-001",
        job_type=ApplicationJobType.AGENT_EXECUTION,
        queue_name="research",
        status=ApplicationJobStatus.PENDING,
        available_at=BASE_TIME,
        created_at=BASE_TIME,
    )


def test_successful_transaction_keeps_changes() -> None:
    executions = InMemoryApplicationExecutionRepository()
    evaluations = InMemoryApplicationEvaluationRepository()

    manager = InMemoryApplicationTransactionManager(
        resources=[
            executions,
            evaluations,
        ]
    )

    with manager.transaction():
        executions.create(execution("execution-001"))
        evaluations.create(evaluation("evaluation-001"))

    assert executions.exists("execution-001") is True
    assert evaluations.exists("evaluation-001") is True


def test_failed_transaction_rolls_back_all_resources() -> None:
    executions = InMemoryApplicationExecutionRepository()
    evaluations = InMemoryApplicationEvaluationRepository()
    jobs = InMemoryApplicationJobRepository()

    manager = InMemoryApplicationTransactionManager(
        resources=[
            executions,
            evaluations,
            jobs,
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="simulated transaction failure",
    ), manager.transaction():
        executions.create(
            execution("execution-001")
        )
        evaluations.create(
            evaluation("evaluation-001")
        )
        jobs.create(job("job-001"))

        raise RuntimeError(
            "simulated transaction failure"
        )

    assert executions.exists("execution-001") is False
    assert evaluations.exists("evaluation-001") is False
    assert jobs.exists("job-001") is False


def test_rollback_restores_existing_record() -> None:
    original = execution("execution-001")
    executions = InMemoryApplicationExecutionRepository(
        [original]
    )

    manager = InMemoryApplicationTransactionManager(
        resources=[executions]
    )

    with pytest.raises(RuntimeError), manager.transaction():
        running = original.model_copy(
            update={
                "status": (
                    ApplicationExecutionStatus.RUNNING
                ),
                "started_at": BASE_TIME,
                "record_version": 2,
            }
        )

        executions.update(
            running,
            expected_version=1,
        )

        raise RuntimeError("rollback")

    restored = executions.require("execution-001")

    assert restored == original
    assert restored.status is (
        ApplicationExecutionStatus.PENDING
    )
    assert restored.record_version == 1


def test_transaction_does_not_rollback_after_commit() -> None:
    executions = InMemoryApplicationExecutionRepository()

    manager = InMemoryApplicationTransactionManager(
        resources=[executions]
    )

    with manager.transaction():
        executions.create(execution("execution-001"))

    with pytest.raises(RuntimeError), manager.transaction():
        executions.create(execution("execution-002"))
        raise RuntimeError("second transaction failed")

    assert executions.exists("execution-001") is True
    assert executions.exists("execution-002") is False


def test_nested_transaction_is_rejected() -> None:
    executions = InMemoryApplicationExecutionRepository()

    manager = InMemoryApplicationTransactionManager(
        resources=[executions]
    )

    with manager.transaction(), pytest.raises(
        ApplicationNestedTransactionError,
        match=(
            "nested application transaction is not "
            "supported"
        ),
    ), manager.transaction():
        pass


def test_transaction_requires_resource() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "transaction manager requires at least "
            "one resource"
        ),
    ):
        InMemoryApplicationTransactionManager(
            resources=[]
        )


def test_duplicate_resource_is_rejected() -> None:
    executions = InMemoryApplicationExecutionRepository()

    with pytest.raises(
        ValueError,
        match="transaction resources must be unique",
    ):
        InMemoryApplicationTransactionManager(
            resources=[
                executions,
                executions,
            ]
        )


def test_snapshot_is_isolated_from_repository() -> None:
    executions = InMemoryApplicationExecutionRepository(
        [execution("execution-001")]
    )

    snapshot = executions.snapshot_state()
    executions.clear()

    assert executions.exists("execution-001") is False

    executions.restore_state(snapshot)

    assert executions.exists("execution-001") is True
