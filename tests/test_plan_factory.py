"""Tests for deterministic agent plan materialization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.memory.clock import Clock
from app.planning.plan_factory import (
    PlanFactory,
    PlanFactoryError,
)
from app.planning.plan_id_generator import (
    PlanIdGenerator,
)
from app.schemas.plan import (
    PlanStatus,
    PlanStepStatus,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_request import (
    PlanCreationRequest,
)

NOW = datetime(
    2026,
    8,
    3,
    15,
    0,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return a configurable datetime."""

    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class FixedPlanIdGenerator(PlanIdGenerator):
    """Return one configured plan ID."""

    def __init__(
        self,
        value: str = "plan-001",
    ) -> None:
        self.value = value

    def generate(self) -> str:
        return self.value


def request(
    **overrides: object,
) -> PlanCreationRequest:
    """Return one valid plan creation request."""

    values: dict[str, object] = {
        "goal": "Build and validate a planning agent.",
        "constraints": ["Run tests."],
        "available_tools": [
            "python",
            "pytest",
        ],
        "maximum_steps": 5,
    }
    values.update(overrides)

    return PlanCreationRequest(**values)


def draft(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
    tool_name: str | None = None,
) -> PlanStepDraft:
    """Return one valid plan step draft."""

    return PlanStepDraft(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete work for {step_id}.",
        dependencies=dependencies or [],
        tool_name=tool_name,
    )


def factory(
    *,
    clock: Clock | None = None,
    plan_id: str = "plan-001",
) -> PlanFactory:
    """Return one deterministic plan factory."""

    return PlanFactory(
        clock=clock or FixedClock(NOW),
        id_generator=FixedPlanIdGenerator(
            plan_id
        ),
    )


def test_factory_assigns_id_and_timestamps() -> None:
    created = factory().create(
        request=request(),
        steps=[
            draft(step_id="step-1")
        ],
    )

    assert created.plan.plan_id == "plan-001"
    assert created.plan.created_at == NOW
    assert created.plan.updated_at == NOW
    assert created.plan.status is PlanStatus.DRAFT


def test_factory_sets_root_steps_ready() -> None:
    created = factory().create(
        request=request(),
        steps=[
            draft(step_id="step-1"),
            draft(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ],
    )

    assert created.plan.steps[0].status is (
        PlanStepStatus.READY
    )
    assert created.plan.steps[1].status is (
        PlanStepStatus.PENDING
    )


def test_factory_returns_initial_validation() -> None:
    created = factory().create(
        request=request(),
        steps=[
            draft(step_id="step-1"),
            draft(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ],
    )

    assert created.validation.valid is True
    assert created.validation.execution_order == [
        "step-1",
        "step-2",
    ]


def test_factory_preserves_request_metadata() -> None:
    created = factory().create(
        request=request(
            metadata={"source": "test"}
        ),
        steps=[
            draft(step_id="step-1")
        ],
    )

    assert created.plan.metadata["source"] == "test"
    assert created.plan.metadata["constraints"] == [
        "Run tests."
    ]
    assert created.plan.metadata[
        "available_tools"
    ] == [
        "python",
        "pytest",
    ]


def test_factory_rejects_empty_steps() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="requires at least one step",
    ):
        factory().create(
            request=request(),
            steps=[],
        )


def test_factory_rejects_too_many_steps() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="exceeds maximum_steps",
    ):
        factory().create(
            request=request(maximum_steps=1),
            steps=[
                draft(step_id="step-1"),
                draft(step_id="step-2"),
            ],
        )


def test_factory_rejects_duplicate_step_ids() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="step IDs must be unique",
    ):
        factory().create(
            request=request(),
            steps=[
                draft(step_id="step-1"),
                draft(step_id="step-1"),
            ],
        )


def test_factory_rejects_unknown_dependency() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="unknown steps",
    ):
        factory().create(
            request=request(),
            steps=[
                draft(
                    step_id="step-1",
                    dependencies=["missing"],
                )
            ],
        )


def test_factory_rejects_unavailable_tool() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="uses unavailable tool",
    ):
        factory().create(
            request=request(),
            steps=[
                draft(
                    step_id="step-1",
                    tool_name="browser",
                )
            ],
        )


def test_factory_requires_tool_when_configured() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="requires a tool",
    ):
        factory().create(
            request=request(
                require_tool_for_each_step=True
            ),
            steps=[
                draft(step_id="step-1")
            ],
        )


def test_factory_accepts_available_tool() -> None:
    created = factory().create(
        request=request(
            require_tool_for_each_step=True
        ),
        steps=[
            draft(
                step_id="step-1",
                tool_name="python",
            )
        ],
    )

    assert created.plan.steps[0].tool_name == (
        "python"
    )


def test_factory_rejects_blank_generated_id() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="blank ID",
    ):
        factory(plan_id=" ").create(
            request=request(),
            steps=[
                draft(step_id="step-1")
            ],
        )


def test_factory_rejects_naive_clock() -> None:
    with pytest.raises(
        PlanFactoryError,
        match="timezone-aware",
    ):
        factory(
            clock=FixedClock(
                NOW.replace(tzinfo=None)
            )
        ).create(
            request=request(),
            steps=[
                draft(step_id="step-1")
            ],
        )


def test_factory_rejects_non_utc_clock() -> None:
    non_utc = NOW.astimezone(
        timezone(timedelta(hours=9))
    )

    with pytest.raises(
        PlanFactoryError,
        match="must return UTC",
    ):
        factory(
            clock=FixedClock(non_utc)
        ).create(
            request=request(),
            steps=[
                draft(step_id="step-1")
            ],
        )


def test_factory_detects_circular_plan() -> None:
    created = factory().create(
        request=request(),
        steps=[
            draft(
                step_id="step-1",
                dependencies=["step-2"],
            ),
            draft(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ],
    )

    assert created.validation.valid is False
    assert created.validation.execution_order == []
