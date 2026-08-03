"""Tests for planning-agent request schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_request import PlanCreationRequest
from app.schemas.plan_run import PlanRunRequest
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)


def test_request_has_default_execution_options() -> None:
    request = PlanningAgentRequest(
        planning=PlanCreationRequest(
            goal="Complete the requested workflow."
        )
    )

    assert request.execution.maximum_cycles == 100


def test_request_accepts_custom_execution_limit() -> None:
    request = PlanningAgentRequest(
        planning=PlanCreationRequest(
            goal="Complete the requested workflow."
        ),
        execution=PlanRunRequest(
            maximum_cycles=5
        ),
    )

    assert request.execution.maximum_cycles == 5


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlanningAgentRequest(
            planning=PlanCreationRequest(
                goal="Complete the requested workflow."
            ),
            unknown_value=True,
        )
