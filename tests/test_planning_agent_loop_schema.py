"""Tests for bounded planning-agent loop schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopRequest,
)
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)


def test_loop_request_has_bounded_default() -> None:
    request = PlanningAgentLoopRequest(
        initial=PlanningAgentRequest(
            planning=PlanCreationRequest(
                goal="Complete the workflow."
            )
        )
    )

    assert request.maximum_replans == 2


def test_loop_request_accepts_zero_replans() -> None:
    request = PlanningAgentLoopRequest(
        initial=PlanningAgentRequest(
            planning=PlanCreationRequest(
                goal="Complete the workflow."
            )
        ),
        maximum_replans=0,
    )

    assert request.maximum_replans == 0


def test_loop_request_rejects_excessive_replans() -> None:
    with pytest.raises(ValidationError):
        PlanningAgentLoopRequest(
            initial=PlanningAgentRequest(
                planning=PlanCreationRequest(
                    goal="Complete the workflow."
                )
            ),
            maximum_replans=11,
        )
