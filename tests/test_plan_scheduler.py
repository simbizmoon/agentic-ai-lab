"""Tests for deterministic executable-step scheduling."""

from datetime import UTC, datetime

from app.planning.plan_scheduler import PlanScheduler
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleRequest,
)

NOW = datetime(
    2026,
    8,
    3,
    17,
    0,
    tzinfo=UTC,
)


def step(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
    status: PlanStepStatus,
) -> PlanStep:
    """Return one plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        dependencies=dependencies or [],
        status=status,
    )


def plan(
    *,
    status: PlanStatus = PlanStatus.IN_PROGRESS,
    steps: list[PlanStep] | None = None,
) -> Plan:
    """Return one plan."""

    return Plan(
        plan_id="plan-001",
        goal="Build a planning agent.",
        status=status,
        steps=steps
        or [
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
            )
        ],
        created_at=NOW,
        updated_at=NOW,
    )


def test_scheduler_selects_first_ready_step() -> None:
    result = PlanScheduler().schedule(
        plan=plan()
    )

    assert result.selected_step_ids == [
        "step-1"
    ]
    assert result.reason is (
        PlanScheduleReason.STEPS_SELECTED
    )


def test_scheduler_selects_parallel_ready_steps() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-3",
                dependencies=[
                    "step-1",
                    "step-2",
                ],
                status=PlanStepStatus.PENDING,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value,
        request=PlanScheduleRequest(
            allow_parallel_steps=True,
            maximum_selected_steps=2,
        ),
    )

    assert result.selected_step_ids == [
        "step-1",
        "step-2",
    ]


def test_scheduler_disables_parallel_selection() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value,
        request=PlanScheduleRequest(
            allow_parallel_steps=False,
            maximum_selected_steps=10,
        ),
    )

    assert result.selected_step_ids == [
        "step-1"
    ]


def test_scheduler_respects_selection_limit() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-3",
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value,
        request=PlanScheduleRequest(
            maximum_selected_steps=2
        ),
    )

    assert result.selected_step_ids == [
        "step-1",
        "step-2",
    ]


def test_scheduler_uses_dependency_execution_order() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value
    )

    assert result.selected_step_ids == [
        "step-2"
    ]


def test_scheduler_rejects_non_running_plan() -> None:
    result = PlanScheduler().schedule(
        plan=plan(status=PlanStatus.DRAFT)
    )

    assert result.selected_step_ids == []
    assert result.reason is (
        PlanScheduleReason.PLAN_NOT_IN_PROGRESS
    )


def test_scheduler_blocks_new_step_when_active_exists() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value
    )

    assert result.selected_step_ids == []
    assert result.active_step_ids == ["step-1"]
    assert result.reason is (
        PlanScheduleReason.ACTIVE_STEP_EXISTS
    )


def test_scheduler_can_select_while_step_is_active() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.READY,
            ),
        ]
    )

    result = PlanScheduler().schedule(
        plan=value,
        request=PlanScheduleRequest(
            allow_new_steps_while_active=True
        ),
    )

    assert result.selected_step_ids == [
        "step-2"
    ]


def test_scheduler_returns_no_ready_steps() -> None:
    value = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            )
        ]
    )

    result = PlanScheduler().schedule(
        plan=value
    )

    assert result.selected_step_ids == []
    assert result.reason is (
        PlanScheduleReason.NO_READY_STEPS
    )


def test_scheduler_does_not_mutate_plan() -> None:
    original = plan()

    result = PlanScheduler().schedule(
        plan=original
    )

    assert result.selected_step_ids == [
        "step-1"
    ]
    assert original.steps[0].status is (
        PlanStepStatus.READY
    )
