"""Tests for deterministic agent plan validation."""

from datetime import UTC, datetime

from app.planning.plan_validator import (
    PlanValidator,
)
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_validation import (
    PlanValidationCode,
    PlanValidationResult,
    PlanValidationSeverity,
)

NOW = datetime(
    2026,
    8,
    3,
    14,
    0,
    tzinfo=UTC,
)


def step(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
    status: PlanStepStatus = PlanStepStatus.PENDING,
) -> PlanStep:
    """Return one valid plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete work for {step_id}.",
        dependencies=dependencies or [],
        status=status,
    )


def plan(
    *,
    steps: list[PlanStep],
    status: PlanStatus = PlanStatus.DRAFT,
) -> Plan:
    """Return one valid plan."""

    return Plan(
        plan_id="plan-001",
        goal="Build a planning agent.",
        status=status,
        steps=steps,
        created_at=NOW,
        updated_at=NOW,
    )


def issue_codes(
    result: PlanValidationResult,
) -> list[PlanValidationCode]:
    """Return validation codes from a result."""

    return [
        issue.code
        for issue in result.issues
    ]


def test_valid_linear_plan_returns_execution_order() -> None:
    value = plan(
        steps=[
            step(step_id="step-1"),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
            step(
                step_id="step-3",
                dependencies=["step-2"],
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is True
    assert result.execution_order == [
        "step-1",
        "step-2",
        "step-3",
    ]


def test_valid_parallel_plan_has_deterministic_order() -> None:
    value = plan(
        steps=[
            step(step_id="step-1"),
            step(step_id="step-2"),
            step(
                step_id="step-3",
                dependencies=[
                    "step-1",
                    "step-2",
                ],
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.execution_order == [
        "step-1",
        "step-2",
        "step-3",
    ]


def test_detects_circular_dependency() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                dependencies=["step-2"],
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is False
    assert (
        PlanValidationCode.CIRCULAR_DEPENDENCY
        in issue_codes(result)
    )
    assert result.execution_order == []


def test_warns_when_list_order_precedes_dependency() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
            step(step_id="step-1"),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is True
    assert (
        PlanValidationCode
        .DEPENDENCY_ORDER_VIOLATION
        in issue_codes(result)
    )
    assert result.execution_order == [
        "step-1",
        "step-2",
    ]


def test_ready_step_requires_completed_dependencies() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.PENDING,
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is False
    assert (
        PlanValidationCode
        .READY_WITH_INCOMPLETE_DEPENDENCY
        in issue_codes(result)
    )


def test_pending_step_warns_when_dependencies_complete() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.PENDING,
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is True

    matching = [
        issue
        for issue in result.issues
        if issue.code
        is PlanValidationCode
        .PENDING_WITH_COMPLETED_DEPENDENCIES
    ]

    assert len(matching) == 1
    assert matching[0].severity is (
        PlanValidationSeverity.WARNING
    )


def test_ready_step_cannot_depend_on_failed_step() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.FAILED,
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanValidator().validate(value)

    assert result.valid is False
    assert (
        PlanValidationCode.DEPENDS_ON_FAILED_STEP
        in issue_codes(result)
    )


def test_completed_plan_requires_completed_steps() -> None:
    value = plan(
        status=PlanStatus.COMPLETED,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.PENDING,
            )
        ],
    )

    result = PlanValidator().validate(value)

    assert result.valid is False
    assert (
        PlanValidationCode
        .COMPLETED_PLAN_HAS_INCOMPLETE_STEPS
        in issue_codes(result)
    )


def test_terminal_plan_rejects_active_step() -> None:
    value = plan(
        status=PlanStatus.CANCELLED,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            )
        ],
    )

    result = PlanValidator().validate(value)

    assert result.valid is False
    assert (
        PlanValidationCode
        .TERMINAL_PLAN_HAS_ACTIVE_STEPS
        in issue_codes(result)
    )


def test_failed_plan_warns_without_failed_step() -> None:
    value = plan(
        status=PlanStatus.FAILED,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            )
        ],
    )

    result = PlanValidator().validate(value)

    assert result.valid is True
    assert (
        PlanValidationCode
        .FAILED_PLAN_HAS_NO_FAILED_STEP
        in issue_codes(result)
    )
