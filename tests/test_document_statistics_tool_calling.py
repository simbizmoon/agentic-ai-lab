"""Tests for the single document-statistics tool workflow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.document_statistics_tool_calling import (
    ToolCallingError,
    answer_with_document_statistics_tool,
)


class FakeResponses:
    """Return predefined Responses API results."""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)

        if not self._responses:
            raise AssertionError("unexpected Responses API call")

        return self._responses.pop(0)


class FakeClient:
    """Minimal fake OpenAI client."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = FakeResponses(responses)


def function_call_response() -> object:
    return SimpleNamespace(
        id="resp_first",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments=(
                    '{"document_text":'
                    '"Agent tools are useful.\\nThey execute code."}'
                ),
                call_id="call_123",
            )
        ],
        output_text="",
    )


def final_response() -> object:
    return SimpleNamespace(
        id="resp_second",
        output=[],
        output_text=(
            "The document has 42 characters, "
            "7 words, and 2 lines."
        ),
    )


def test_tool_calling_executes_tool_and_returns_final_text() -> None:
    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = answer_with_document_statistics_tool(
        client=client,
        model="test-model",
        user_request=(
            "Count the characters, words, and lines in this text: "
            "Agent tools are useful.\nThey execute code."
        ),
    )

    assert result == (
        "The document has 42 characters, "
        "7 words, and 2 lines."
    )
    assert len(client.responses.calls) == 2

    first_call = client.responses.calls[0]
    second_call = client.responses.calls[1]

    assert first_call["tool_choice"] == "auto"
    assert first_call["parallel_tool_calls"] is False

    assert second_call["previous_response_id"] == "resp_first"
    assert second_call["tool_choice"] == "none"

    tool_output = second_call["input"][0]

    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call_123"
    assert '"ok": true' in tool_output["output"]
    assert '"character_count": 42' in tool_output["output"]
    assert '"word_count": 7' in tool_output["output"]
    assert '"line_count": 2' in tool_output["output"]


def test_tool_calling_returns_direct_answer_when_no_tool_is_used() -> None:
    direct_response = SimpleNamespace(
        id="resp_direct",
        output=[],
        output_text="This request does not require document statistics.",
    )
    client = FakeClient([direct_response])

    result = answer_with_document_statistics_tool(
        client=client,
        model="test-model",
        user_request="Explain what a local tool is.",
    )

    assert result == (
        "This request does not require document statistics."
    )
    assert len(client.responses.calls) == 1


def test_tool_calling_rejects_multiple_function_calls() -> None:
    response = SimpleNamespace(
        id="resp_multiple",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"first"}',
                call_id="call_1",
            ),
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"second"}',
                call_id="call_2",
            ),
        ],
        output_text="",
    )
    client = FakeClient([response])

    with pytest.raises(
        ToolCallingError,
        match="exactly one function call",
    ):
        answer_with_document_statistics_tool(
            client=client,
            model="test-model",
            user_request="Count both documents.",
        )


def test_tool_calling_rejects_empty_request() -> None:
    client = FakeClient([])

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        answer_with_document_statistics_tool(
            client=client,
            model="test-model",
            user_request="   ",
        )


def test_tool_calling_corrects_invalid_arguments_once() -> None:
    invalid_response = SimpleNamespace(
        id="resp_invalid",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid",
            )
        ],
        output_text="",
    )
    corrected_response = SimpleNamespace(
        id="resp_corrected",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"corrected text"}',
                call_id="call_corrected",
            )
        ],
        output_text="",
    )
    client = FakeClient(
        [
            invalid_response,
            corrected_response,
            final_response(),
        ]
    )

    result = answer_with_document_statistics_tool(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert result == (
        "The document has 42 characters, "
        "7 words, and 2 lines."
    )
    assert len(client.responses.calls) == 3

    correction_call = client.responses.calls[1]
    error_output = correction_call["input"][0]["output"]

    assert correction_call["tool_choice"] == "auto"
    assert correction_call["parallel_tool_calls"] is False
    assert '"ok": false' in error_output
    assert '"argument_validation_failed"' in error_output

    final_call = client.responses.calls[2]

    assert final_call["previous_response_id"] == (
        "resp_corrected"
    )
    assert final_call["tool_choice"] == "none"


def test_tool_calling_does_not_retry_unsupported_tool() -> None:
    response = SimpleNamespace(
        id="resp_unsupported",
        output=[
            SimpleNamespace(
                type="function_call",
                name="delete_all_files",
                arguments="{}",
                call_id="call_forbidden",
            )
        ],
        output_text="",
    )
    client = FakeClient([response])

    with pytest.raises(ToolCallingError) as exc_info:
        answer_with_document_statistics_tool(
            client=client,
            model="test-model",
            user_request="Delete everything.",
        )

    assert exc_info.value.code.value == "tool_call_failed"
    assert len(client.responses.calls) == 1


def test_tool_calling_stops_after_failed_correction() -> None:
    invalid_response = SimpleNamespace(
        id="resp_invalid",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid",
            )
        ],
        output_text="",
    )
    still_invalid_response = SimpleNamespace(
        id="resp_still_invalid",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":""}',
                call_id="call_still_invalid",
            )
        ],
        output_text="",
    )
    client = FakeClient(
        [
            invalid_response,
            still_invalid_response,
        ]
    )

    with pytest.raises(ToolCallingError) as exc_info:
        answer_with_document_statistics_tool(
            client=client,
            model="test-model",
            user_request="Count the supplied document.",
        )

    assert (
        exc_info.value.code.value
        == "tool_correction_failed"
    )
    assert len(client.responses.calls) == 2


def test_workflow_result_preserves_observation() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_statistics_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_statistics_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert result.tool_used is True
    assert result.tool_name == "get_document_statistics"
    assert result.observation == {
        "character_count": 42,
        "word_count": 7,
        "line_count": 2,
    }
    assert result.final_answer == (
        "The document has 42 characters, "
        "7 words, and 2 lines."
    )


def test_workflow_result_preserves_direct_answer() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_statistics_tool_workflow,
    )

    direct_response = SimpleNamespace(
        id="resp_direct",
        output=[],
        output_text="A Tool was not required.",
    )
    client = FakeClient([direct_response])

    result = run_document_statistics_tool_workflow(
        client=client,
        model="test-model",
        user_request="Explain Tool Calling.",
    )

    assert result.tool_used is False
    assert result.tool_name is None
    assert result.observation is None
    assert result.final_answer == "A Tool was not required."
