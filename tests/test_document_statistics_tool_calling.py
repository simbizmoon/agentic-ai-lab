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


def keyword_function_call_response() -> object:
    """Return a model response selecting the keyword Tool."""

    return SimpleNamespace(
        id="resp_keywords",
        output=[
            SimpleNamespace(
                type="function_call",
                name="extract_document_keywords",
                arguments=(
                    '{"document_text":'
                    '"agent tool agent workflow",'
                    '"max_keywords":2}'
                ),
                call_id="call_keywords",
            )
        ],
        output_text="",
    )


def keyword_final_response() -> object:
    """Return the model answer after keyword observation."""

    return SimpleNamespace(
        id="resp_keywords_final",
        output=[],
        output_text=(
            "The most frequent keywords are "
            "agent and tool."
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
        match="at most one Tool call",
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


def test_tool_calling_uses_allowed_registry_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import (
        document_statistics_tool_calling as service,
    )

    custom_schema = {
        "type": "function",
        "name": "registry_tool",
        "description": "Registry test Tool.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    }

    monkeypatch.setattr(
        service,
        "get_allowed_tool_schemas",
        lambda: [custom_schema],
    )

    direct_response = SimpleNamespace(
        id="resp_direct",
        output=[],
        output_text="No Tool was required.",
    )
    client = FakeClient([direct_response])

    result = service.run_document_statistics_tool_workflow(
        client=client,
        model="test-model",
        user_request="Explain Tool Calling.",
    )

    assert result.tool_used is False
    assert client.responses.calls[0]["tools"] == [
        custom_schema
    ]


def test_workflow_executes_keyword_tool() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_statistics_tool_workflow,
    )

    client = FakeClient(
        [
            keyword_function_call_response(),
            keyword_final_response(),
        ]
    )

    result = run_document_statistics_tool_workflow(
        client=client,
        model="test-model",
        user_request=(
            "Extract the two most frequent keywords from: "
            "agent tool agent workflow"
        ),
    )

    assert result.tool_used is True
    assert result.tool_name == "extract_document_keywords"
    assert result.observation == {
        "keywords": [
            {
                "keyword": "agent",
                "count": 2,
            },
            {
                "keyword": "tool",
                "count": 1,
            },
        ]
    }
    assert result.final_answer == (
        "The most frequent keywords are "
        "agent and tool."
    )

    assert len(client.responses.calls) == 2

    first_call = client.responses.calls[0]
    final_call = client.responses.calls[1]

    assert first_call["tool_choice"] == "auto"
    assert first_call["parallel_tool_calls"] is False

    tool_output = final_call["input"][0]

    assert tool_output["call_id"] == "call_keywords"
    assert '"keyword": "agent"' in tool_output["output"]
    assert '"count": 2' in tool_output["output"]
    assert final_call["tool_choice"] == "none"


def test_generalized_workflow_name_executes_statistics_tool() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert result.tool_used is True
    assert result.tool_name == "get_document_statistics"


def test_generalized_answer_helper_executes_keyword_tool() -> None:
    from app.services.document_statistics_tool_calling import (
        answer_with_document_tools,
    )

    client = FakeClient(
        [
            keyword_function_call_response(),
            keyword_final_response(),
        ]
    )

    answer = answer_with_document_tools(
        client=client,
        model="test-model",
        user_request="Extract the document keywords.",
    )

    assert answer == (
        "The most frequent keywords are "
        "agent and tool."
    )


def test_legacy_workflow_wrapper_remains_compatible() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_statistics_tool_workflow,
    )

    client = FakeClient(
        [
            keyword_function_call_response(),
            keyword_final_response(),
        ]
    )

    result = run_document_statistics_tool_workflow(
        client=client,
        model="test-model",
        user_request="Extract the document keywords.",
    )

    assert result.tool_name == "extract_document_keywords"


def test_compound_request_can_return_direct_limitation_message() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    direct_response = SimpleNamespace(
        id="resp_compound",
        output=[],
        output_text=(
            "This workflow currently supports one Tool operation "
            "per request. Please request document statistics and "
            "keyword extraction separately."
        ),
    )
    client = FakeClient([direct_response])

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request=(
            "Calculate the document statistics and also extract "
            "the five most frequent keywords."
        ),
    )

    assert result.tool_used is False
    assert result.tool_name is None
    assert result.observation is None
    assert "one Tool operation per request" in result.final_answer
    assert len(client.responses.calls) == 1


def test_tool_instructions_define_compound_request_policy() -> None:
    from app.services.document_statistics_tool_calling import (
        TOOL_INSTRUCTIONS,
    )

    assert "multiple operations" in TOOL_INSTRUCTIONS
    assert "do not call any Tool" in TOOL_INSTRUCTIONS
    assert "separate requests" in TOOL_INSTRUCTIONS


def test_workflow_records_successful_tool_events() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert [
        event.event_type.value
        for event in result.events
    ] == [
        "request_received",
        "tool_selected",
        "tool_execution_succeeded",
        "final_response_created",
    ]
    assert result.events[1].tool_name == (
        "get_document_statistics"
    )


def test_workflow_records_direct_response_events() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    direct_response = SimpleNamespace(
        id="resp_direct_events",
        output=[],
        output_text="No Tool was needed.",
    )
    client = FakeClient([direct_response])

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Explain a concept.",
    )

    assert [
        event.event_type.value
        for event in result.events
    ] == [
        "request_received",
        "direct_response",
    ]


def test_workflow_records_argument_correction_events() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    invalid_response = SimpleNamespace(
        id="resp_invalid_events",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid_events",
            )
        ],
        output_text="",
    )
    corrected_response = SimpleNamespace(
        id="resp_corrected_events",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"corrected text"}',
                call_id="call_corrected_events",
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

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert [
        event.event_type.value
        for event in result.events
    ] == [
        "request_received",
        "tool_selected",
        "tool_argument_correction_requested",
        "tool_arguments_corrected",
        "tool_execution_succeeded",
        "final_response_created",
    ]
    assert result.events[2].details == {
        "error_code": "argument_validation_failed"
    }


def test_workflow_records_nonnegative_elapsed_times() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert result.events
    assert all(
        event.elapsed_ms >= 0.0
        for event in result.events
    )


def test_workflow_elapsed_times_are_monotonic() -> None:
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    elapsed_times = [
        event.elapsed_ms
        for event in result.events
    ]

    assert elapsed_times == sorted(elapsed_times)


def test_elapsed_ms_uses_performance_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import (
        document_statistics_tool_calling as service,
    )

    counter_values = iter(
        [
            1_125_500_000,
        ]
    )

    monkeypatch.setattr(
        service.time,
        "perf_counter_ns",
        lambda: next(counter_values),
    )

    assert service._elapsed_ms(1_000_000_000) == 125.5


def test_successful_workflow_exposes_completed_status() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    client = FakeClient(
        [
            function_call_response(),
            final_response(),
        ]
    )

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert (
        result.workflow_status
        == DocumentWorkflowStatus.COMPLETED
    )
    assert result.correction_attempted is False


def test_corrected_workflow_exposes_correction_attempt() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        run_document_tool_workflow,
    )

    invalid_response = SimpleNamespace(
        id="resp_invalid_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid_state",
            )
        ],
        output_text="",
    )
    corrected_response = SimpleNamespace(
        id="resp_corrected_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"corrected text"}',
                call_id="call_corrected_state",
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

    result = run_document_tool_workflow(
        client=client,
        model="test-model",
        user_request="Count the supplied document.",
    )

    assert (
        result.workflow_status
        == DocumentWorkflowStatus.COMPLETED
    )
    assert result.correction_attempted is True


def test_workflow_error_preserves_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowState,
        DocumentWorkflowStatus,
    )
    from app.services import (
        document_statistics_tool_calling as service,
    )

    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Analyze the document.",
    )
    state = service.start_model_decision(state)

    error = service._workflow_error(
        state,
        code=service.ToolCallingErrorCode.INVALID_RESPONSE,
        safe_message="The model response was invalid.",
    )

    assert (
        error.code
        == service.ToolCallingErrorCode.INVALID_RESPONSE
    )
    assert error.failure is not None
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.error_code == "invalid_response"
    assert error.failure.state.error_message == (
        "The model response was invalid."
    )


def test_legacy_tool_calling_error_can_omit_failure() -> None:
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        ToolCallingErrorCode,
    )

    error = ToolCallingError(
        code=ToolCallingErrorCode.INVALID_RESPONSE,
        safe_message="Invalid response.",
    )

    assert error.failure is None


def test_unsupported_tool_error_preserves_failed_workflow_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    response = SimpleNamespace(
        id="resp_unsupported_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="delete_all_files",
                arguments="{}",
                call_id="call_forbidden_state",
            )
        ],
        output_text="",
    )
    client = FakeClient([response])

    with pytest.raises(ToolCallingError) as exc_info:
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Delete everything.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.selected_tool_name == (
        "delete_all_files"
    )
    assert error.failure.state.tool_call_id == (
        "call_forbidden_state"
    )
    assert error.failure.state.error_code == (
        "tool_call_failed"
    )
    assert error.failure.state.error_message == (
        "unsupported tool: delete_all_files"
    )


def test_missing_corrected_call_preserves_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    invalid_response = SimpleNamespace(
        id="resp_invalid_correction_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid_correction_state",
            )
        ],
        output_text="",
    )
    no_correction_response = SimpleNamespace(
        id="resp_no_correction_state",
        output=[],
        output_text="I could not correct the arguments.",
    )
    client = FakeClient(
        [
            invalid_response,
            no_correction_response,
        ]
    )

    with pytest.raises(ToolCallingError) as exc_info:
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Count the supplied document.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.correction_attempted is True
    assert error.failure.state.selected_tool_name == (
        "get_document_statistics"
    )
    assert error.failure.state.error_code == (
        "tool_correction_failed"
    )


def test_failed_corrected_tool_preserves_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    invalid_response = SimpleNamespace(
        id="resp_invalid_retry_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"   "}',
                call_id="call_invalid_retry_state",
            )
        ],
        output_text="",
    )
    still_invalid_response = SimpleNamespace(
        id="resp_still_invalid_retry_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":""}',
                call_id="call_still_invalid_retry_state",
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
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Count the supplied document.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.correction_attempted is True
    assert error.failure.state.tool_call_id == (
        "call_still_invalid_retry_state"
    )
    assert error.failure.state.error_code == (
        "tool_correction_failed"
    )


def test_multiple_tool_calls_preserve_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    response = SimpleNamespace(
        id="resp_multiple_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_document_statistics",
                arguments='{"document_text":"first"}',
                call_id="call_multiple_1",
            ),
            SimpleNamespace(
                type="function_call",
                name="extract_document_keywords",
                arguments=(
                    '{"document_text":"second",'
                    '"max_keywords":5}'
                ),
                call_id="call_multiple_2",
            ),
        ],
        output_text="",
    )
    client = FakeClient([response])

    with pytest.raises(ToolCallingError) as exc_info:
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Run both document operations.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert error.code.value == "multiple_tool_calls"
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.error_code == (
        "multiple_tool_calls"
    )
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )


def test_invalid_function_call_preserves_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    response = SimpleNamespace(
        id="resp_invalid_function_state",
        output=[
            SimpleNamespace(
                type="function_call",
                name="",
                arguments="{}",
                call_id="call_invalid_function_state",
            )
        ],
        output_text="",
    )
    client = FakeClient([response])

    with pytest.raises(ToolCallingError) as exc_info:
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Analyze the document.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert error.code.value == "invalid_function_call"
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.error_code == (
        "invalid_function_call"
    )


def test_missing_final_text_preserves_failed_state() -> None:
    from app.schemas.document_workflow_state import (
        DocumentWorkflowStatus,
    )
    from app.services.document_statistics_tool_calling import (
        ToolCallingError,
        run_document_tool_workflow,
    )

    missing_text_response = SimpleNamespace(
        id="resp_missing_final_state",
        output=[],
        output_text="",
    )
    client = FakeClient(
        [
            function_call_response(),
            missing_text_response,
        ]
    )

    with pytest.raises(ToolCallingError) as exc_info:
        run_document_tool_workflow(
            client=client,
            model="test-model",
            user_request="Count the document.",
        )

    error = exc_info.value

    assert error.failure is not None
    assert error.code.value == "missing_final_text"
    assert (
        error.failure.state.status
        == DocumentWorkflowStatus.FAILED
    )
    assert error.failure.state.selected_tool_name == (
        "get_document_statistics"
    )
    assert error.failure.state.observation is not None
    assert error.failure.state.error_code == (
        "missing_final_text"
    )
