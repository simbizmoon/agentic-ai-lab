"""Tests for the OpenAI structured planner client."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.planning.openai_planner_client import (
    OpenAIPlannerClient,
)
from app.planning.planner_client import PlannerClientError
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)


class FakeResponses:
    """Record requests and return one configured response."""

    def __init__(
        self,
        *,
        output_text: object,
        response_id: str = "resp-001",
        model: str = "gpt-5-mini",
    ) -> None:
        self.output_text = output_text
        self.response_id = response_id
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def create(
        self,
        **kwargs: Any,
    ) -> object:
        self.calls.append(kwargs)

        return SimpleNamespace(
            id=self.response_id,
            model=self.model,
            output_text=self.output_text,
        )


class FakeOpenAI:
    """Expose one fake Responses resource."""

    def __init__(
        self,
        responses: FakeResponses,
    ) -> None:
        self.responses = responses


def request(
    **overrides: object,
) -> PlanCreationRequest:
    """Return one planning request."""

    values: dict[str, object] = {
        "goal": "Run and verify the test suite.",
        "available_tools": ["pytest"],
        "maximum_steps": 3,
        "require_tool_for_each_step": True,
    }
    values.update(overrides)

    return PlanCreationRequest(**values)


def valid_output_json() -> str:
    """Return one valid structured planner output."""

    return json.dumps(
        {
            "reasoning_summary": (
                "A single test step satisfies the goal."
            ),
            "steps": [
                {
                    "step_id": "step-1",
                    "title": "Run tests",
                    "description": (
                        "Run the complete test suite."
                    ),
                    "dependencies": [],
                    "tool_name": "pytest",
                    "expected_output": (
                        "All tests pass."
                    ),
                    "metadata": {},
                }
            ],
            "assumptions": [],
            "warnings": [],
        }
    )


def client(
    responses: FakeResponses,
    *,
    config: PlannerClientConfig | None = None,
) -> OpenAIPlannerClient:
    """Return one client with an injected fake API."""

    return OpenAIPlannerClient(
        client=FakeOpenAI(responses),
        config=config,
    )


def test_client_parses_and_validates_output() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    result = client(responses).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    assert result.output.steps[0].step_id == "step-1"
    assert result.validation.valid is True
    assert result.response_id == "resp-001"


def test_client_sends_strict_json_schema() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    client(responses).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    call = responses.calls[0]
    output_format = call["text"]["format"]

    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert output_format["name"] == (
        "plan_draft_output"
    )
    assert "schema" in output_format


def test_client_sends_system_and_user_messages() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    client(responses).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    assert [
        message["role"]
        for message in responses.calls[0]["input"]
    ] == [
        "system",
        "user",
    ]


def test_client_disables_response_storage() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    client(responses).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    assert responses.calls[0]["store"] is False


def test_client_can_omit_reasoning_argument() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    client(
        responses,
        config=PlannerClientConfig(
            reasoning_effort=None
        ),
    ).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    assert "reasoning" not in responses.calls[0]


def test_client_rejects_blank_output() -> None:
    responses = FakeResponses(output_text=" ")
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    with pytest.raises(
        PlannerClientError,
        match="blank output",
    ):
        client(responses).create_plan(
            request=plan_request,
            prompt=prompt,
        )


def test_client_rejects_missing_output_text() -> None:
    responses = FakeResponses(output_text=None)
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    with pytest.raises(
        PlannerClientError,
        match="did not contain output_text",
    ):
        client(responses).create_plan(
            request=plan_request,
            prompt=prompt,
        )


def test_client_rejects_invalid_json_output() -> None:
    responses = FakeResponses(
        output_text="not-json"
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    with pytest.raises(
        PlannerClientError,
        match="failed PlanDraftOutput validation",
    ):
        client(responses).create_plan(
            request=plan_request,
            prompt=prompt,
        )


def test_client_returns_invalid_policy_validation() -> None:
    data = json.loads(valid_output_json())
    data["steps"][0]["tool_name"] = "browser"

    responses = FakeResponses(
        output_text=json.dumps(data)
    )
    plan_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        plan_request
    )

    result = client(responses).create_plan(
        request=plan_request,
        prompt=prompt,
    )

    assert result.validation.valid is False


def test_client_rejects_prompt_request_mismatch() -> None:
    responses = FakeResponses(
        output_text=valid_output_json()
    )
    original_request = request()
    prompt = PlannerPromptComposer().compose_initial(
        original_request
    )
    changed_request = request(maximum_steps=2)

    with pytest.raises(
        PlannerClientError,
        match="maximum_steps does not match",
    ):
        client(responses).create_plan(
            request=changed_request,
            prompt=prompt,
        )

    assert responses.calls == []
