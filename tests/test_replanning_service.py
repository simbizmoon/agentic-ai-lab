"""Tests for replacement-plan creation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.planning.plan_factory import PlanFactory
from app.planning.plan_id_generator import (
    PlanIdGenerator,
)
from app.planning.planner_client import PlannerClient
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.planning.replanning_service import (
    ReplanningService,
    ReplanningServiceError,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
)
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
from app.schemas.planner_prompt import (
    PlannerPrompt,
    PlannerPromptKind,
)
from app.schemas.replan import ReplanRequest

NOW = datetime(
    2026,
    8,
    4,
    0,
    10,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed timestamp."""

    def now(self) -> datetime:
        return NOW


class FixedIdGenerator(PlanIdGenerator):
    """Return one replacement-plan ID."""

    def generate(self) -> str:
        return "plan-002"


class FakePlannerClient(PlannerClient):
    """Return one configured replacement output."""

    def __init__(
        self,
        *,
        valid: bool = True,
    ) -> None:
        self.valid = valid
        self.prompt: PlannerPrompt | None = None
        self.request: PlanCreationRequest | None = None

    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        self.request = request
        self.prompt = prompt

        if self.valid:
            validation = PlannerOutputValidationResult(
                valid=True,
                issues=[],
                execution_order=["step-1"],
            )
        else:
            validation = PlannerOutputValidationResult(
                valid=False,
                issues=[
                    PlannerOutputValidationIssue(
                        code=(
                            PlannerOutputValidationCode
                            .TOOL_NOT_AVAILABLE
                        ),
                        message="Tool unavailable.",
                        step_id="step-1",
                    )
                ],
                execution_order=["step-1"],
            )

        return PlannerClientResult(
            output=PlanDraftOutput(
                reasoning_summary="Use a safer approach.",
                steps=[
                    PlanStepDraft(
                        step_id="step-1",
                        title="Retry safely",
                        description="Use the safe approach.",
                        tool_name="python",
                    )
                ],
            ),
            validation=validation,
        )


def replan_request() -> ReplanRequest:
    """Return one replacement-plan request."""

    return ReplanRequest(
        original_plan_id="plan-001",
        goal="Complete the operation.",
        evaluation_decision=(
            PlanEvaluationDecision.REPLAN_REQUIRED
        ),
        evaluation_codes=[
            PlanEvaluationCode.STEP_EXECUTION_FAILED
        ],
        evaluation_summary="The original step failed.",
        constraints=["Use a safer approach."],
        available_tools=["python"],
        maximum_steps=3,
        previous_cycle_count=1,
    )


def service(
    client: FakePlannerClient,
) -> ReplanningService:
    """Return one deterministic replanning service."""

    return ReplanningService(
        prompt_composer=PlannerPromptComposer(),
        planner_client=client,
        plan_factory=PlanFactory(
            clock=FixedClock(),
            id_generator=FixedIdGenerator(),
        ),
    )


def test_service_creates_replacement_plan() -> None:
    client = FakePlannerClient()

    result = service(client).create_plan(
        replan_request()
    )

    assert result.created_plan.plan.plan_id == (
        "plan-002"
    )
    assert result.prompt.kind is PlannerPromptKind.REPLAN
    assert result.prompt.source_plan_id == "plan-001"
    assert client.request is not None
    assert client.request.maximum_steps == 3


def test_service_rejects_invalid_replanner_output() -> None:
    with pytest.raises(
        ReplanningServiceError,
        match="failed policy validation",
    ):
        service(
            FakePlannerClient(valid=False)
        ).create_plan(replan_request())
