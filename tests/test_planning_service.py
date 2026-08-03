"""Tests for integrated structured plan creation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.planning.plan_factory import PlanFactory
from app.planning.plan_id_generator import (
    PlanIdGenerator,
)
from app.planning.planner_client import (
    PlannerClient,
    PlannerClientError,
)
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.planning.planning_service import (
    PlanningService,
    PlanningServiceError,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationCode,
    PlannerOutputValidationIssue,
    PlannerOutputValidationResult,
)
from app.schemas.planner_prompt import PlannerPrompt

NOW = datetime(
    2026,
    8,
    3,
    22,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed UTC timestamp."""

    def now(self) -> datetime:
        return NOW


class FixedPlanIdGenerator(PlanIdGenerator):
    """Return one fixed plan ID."""

    def generate(self) -> str:
        return "plan-001"


class FakePlannerClient(PlannerClient):
    """Return one configured planner result."""

    def __init__(
        self,
        result: PlannerClientResult | None = None,
        error: PlannerClientError | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[
            tuple[PlanCreationRequest, PlannerPrompt]
        ] = []

    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        self.calls.append((request, prompt))

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise AssertionError(
                "fake planner result was not configured"
            )

        return self.result


def request() -> PlanCreationRequest:
    """Return one valid planning request."""

    return PlanCreationRequest(
        goal="Build and test the feature.",
        constraints=["Run all tests."],
        available_tools=["python", "pytest"],
        maximum_steps=5,
    )


def valid_planner_result() -> PlannerClientResult:
    """Return one valid planner result."""

    return PlannerClientResult(
        output=PlanDraftOutput(
            reasoning_summary=(
                "Implementation must precede testing."
            ),
            steps=[
                PlanStepDraft(
                    step_id="step-1",
                    title="Implement feature",
                    description="Create the implementation.",
                    tool_name="python",
                    expected_output="Implemented feature.",
                ),
                PlanStepDraft(
                    step_id="step-2",
                    title="Run tests",
                    description="Run the complete test suite.",
                    dependencies=["step-1"],
                    tool_name="pytest",
                    expected_output="All tests pass.",
                ),
            ],
        ),
        validation=PlannerOutputValidationResult(
            valid=True,
            issues=[],
            execution_order=[
                "step-1",
                "step-2",
            ],
        ),
        response_id="resp-001",
        model="gpt-5-mini",
    )


def invalid_planner_result() -> PlannerClientResult:
    """Return one policy-invalid planner result."""

    return PlannerClientResult(
        output=PlanDraftOutput(
            reasoning_summary="Use an unavailable tool.",
            steps=[
                PlanStepDraft(
                    step_id="step-1",
                    title="Browse",
                    description="Browse external data.",
                    tool_name="browser",
                )
            ],
        ),
        validation=PlannerOutputValidationResult(
            valid=False,
            issues=[
                PlannerOutputValidationIssue(
                    code=(
                        PlannerOutputValidationCode
                        .TOOL_NOT_AVAILABLE
                    ),
                    message="Browser is unavailable.",
                    step_id="step-1",
                )
            ],
            execution_order=["step-1"],
        ),
    )


def service(
    client: PlannerClient,
) -> PlanningService:
    """Return one deterministic planning service."""

    return PlanningService(
        prompt_composer=PlannerPromptComposer(),
        planner_client=client,
        plan_factory=PlanFactory(
            clock=FixedClock(),
            id_generator=FixedPlanIdGenerator(),
        ),
    )


def test_service_creates_materialized_plan() -> None:
    client = FakePlannerClient(
        result=valid_planner_result()
    )

    result = service(client).create_plan(request())

    assert result.created_plan.plan.plan_id == (
        "plan-001"
    )
    assert result.created_plan.plan.created_at == NOW
    assert [
        step.status.value
        for step in result.created_plan.plan.steps
    ] == [
        "ready",
        "pending",
    ]
    assert result.created_plan.validation.valid is True


def test_service_preserves_planner_metadata() -> None:
    result = service(
        FakePlannerClient(
            result=valid_planner_result()
        )
    ).create_plan(request())

    assert result.planner_result.response_id == (
        "resp-001"
    )
    assert result.planner_result.model == "gpt-5-mini"


def test_service_passes_composed_prompt_to_client() -> None:
    client = FakePlannerClient(
        result=valid_planner_result()
    )
    plan_request = request()

    result = service(client).create_plan(plan_request)

    assert len(client.calls) == 1
    assert client.calls[0][0] == plan_request
    assert client.calls[0][1] == result.prompt


def test_service_rejects_policy_invalid_output() -> None:
    with pytest.raises(
        PlanningServiceError,
        match="failed policy validation",
    ):
        service(
            FakePlannerClient(
                result=invalid_planner_result()
            )
        ).create_plan(request())


def test_service_wraps_planner_client_error() -> None:
    with pytest.raises(
        PlanningServiceError,
        match="planner client failed",
    ):
        service(
            FakePlannerClient(
                error=PlannerClientError(
                    "API failed."
                )
            )
        ).create_plan(request())


def test_service_does_not_call_factory_after_invalid_output() -> None:
    client = FakePlannerClient(
        result=invalid_planner_result()
    )

    with pytest.raises(PlanningServiceError):
        service(client).create_plan(request())

    assert len(client.calls) == 1
