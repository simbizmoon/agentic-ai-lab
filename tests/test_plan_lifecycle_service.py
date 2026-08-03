"""Tests for structured plan lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.planning.plan_lifecycle_service import (
    PlanLifecycleError,
    PlanLifecycleService,
)
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)

CREATED_AT = datetime(
    2026,
    8,
    3,
    16,
    0,
    tzinfo=UTC,
)
UPDATED_AT = datetime(
    2026,
    8,
    3,
    16,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed UTC datetime."""

    def now(self) -> datetime:
        return UPDATED_AT


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
    status: PlanStatus = PlanStatus.DRAFT,
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
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def service() -> PlanLifecycleService:
    """Return one deterministic lifecycle service."""

    return PlanLifecycleService(
        clock=FixedClock()
    )


def test_start_plan_moves_draft_to_in_progress() -> None:
    result = service().start_plan(plan())

    assert result.plan.status is (
        PlanStatus.IN_PROGRESS
    )
    assert result.plan.updated_at == UPDATED_AT
    assert result.changed_step_ids == []


def test_start_plan_rejects_in_progress_plan() -> None:
    with pytest.raises(
        PlanLifecycleError,
        match="draft or ready",
    ):
        service().start_plan(
            plan(status=PlanStatus.IN_PROGRESS)
        )


def test_start_step_moves_ready_step_to_in_progress() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
    )

    result = service().start_step(
        value,
        step_id="step-1",
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.IN_PROGRESS
    )
    assert result.changed_step_ids == ["step-1"]


def test_start_step_requires_in_progress_plan() -> None:
    with pytest.raises(
        PlanLifecycleError,
        match="plan must be in progress",
    ):
        service().start_step(
            plan(),
            step_id="step-1",
        )


def test_start_step_requires_ready_step() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.PENDING,
            )
        ],
    )

    with pytest.raises(
        PlanLifecycleError,
        match="must be ready",
    ):
        service().start_step(
            value,
            step_id="step-1",
        )


def test_complete_step_unlocks_dependent_step() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.PENDING,
            ),
        ],
    )

    result = service().complete_step(
        value,
        step_id="step-1",
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
    assert result.plan.steps[1].status is (
        PlanStepStatus.READY
    )
    assert result.changed_step_ids == [
        "step-1",
        "step-2",
    ]
    assert result.plan.status is (
        PlanStatus.IN_PROGRESS
    )


def test_complete_last_step_completes_plan() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            )
        ],
    )

    result = service().complete_step(
        value,
        step_id="step-1",
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
    assert result.plan.status is PlanStatus.COMPLETED


def test_complete_step_requires_in_progress_status() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
    )

    with pytest.raises(
        PlanLifecycleError,
        match="must be in progress",
    ):
        service().complete_step(
            value,
            step_id="step-1",
        )


def test_fail_step_fails_plan() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.IN_PROGRESS,
            )
        ],
    )

    result = service().fail_step(
        value,
        step_id="step-1",
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.FAILED
    )
    assert result.plan.status is PlanStatus.FAILED


def test_skip_step_unlocks_dependent_step() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
            ),
            step(
                step_id="step-2",
                dependencies=["step-1"],
                status=PlanStepStatus.PENDING,
            ),
        ],
    )

    result = service().skip_step(
        value,
        step_id="step-1",
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.SKIPPED
    )
    assert result.plan.steps[1].status is (
        PlanStepStatus.READY
    )


def test_skip_only_step_completes_plan() -> None:
    result = service().skip_step(
        plan(status=PlanStatus.IN_PROGRESS),
        step_id="step-1",
    )

    assert result.plan.status is PlanStatus.COMPLETED
    assert result.plan.steps[0].status is (
        PlanStepStatus.SKIPPED
    )


def test_cancel_plan_skips_unfinished_steps() -> None:
    value = plan(
        status=PlanStatus.IN_PROGRESS,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            ),
            step(
                step_id="step-2",
                status=PlanStepStatus.IN_PROGRESS,
            ),
            step(
                step_id="step-3",
                dependencies=["step-2"],
                status=PlanStepStatus.PENDING,
            ),
        ],
    )

    result = service().cancel_plan(value)

    assert result.plan.status is PlanStatus.CANCELLED
    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
    assert result.plan.steps[1].status is (
        PlanStepStatus.SKIPPED
    )
    assert result.plan.steps[2].status is (
        PlanStepStatus.SKIPPED
    )
    assert result.changed_step_ids == [
        "step-2",
        "step-3",
    ]


def test_terminal_plan_rejects_operations() -> None:
    value = plan(
        status=PlanStatus.COMPLETED,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.COMPLETED,
            )
        ],
    )

    with pytest.raises(
        PlanLifecycleError,
        match="already terminal",
    ):
        service().cancel_plan(value)


def test_unknown_step_is_rejected() -> None:
    with pytest.raises(
        PlanLifecycleError,
        match="unknown plan step",
    ):
        service().start_step(
            plan(status=PlanStatus.IN_PROGRESS),
            step_id="missing",
        )


def test_original_plan_is_not_mutated() -> None:
    original = plan(
        status=PlanStatus.IN_PROGRESS,
    )

    result = service().start_step(
        original,
        step_id="step-1",
    )

    assert original.steps[0].status is (
        PlanStepStatus.READY
    )
    assert result.plan.steps[0].status is (
        PlanStepStatus.IN_PROGRESS
    )
