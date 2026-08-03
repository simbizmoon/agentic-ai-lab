"""Single-call Responses API workflow for registered document tools."""

from __future__ import annotations

import json
import time
from enum import StrEnum
from typing import Any

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.schemas.tool_workflow_event import (
    ToolWorkflowEvent,
    ToolWorkflowEventType,
)
from app.schemas.tool_workflow_result import ToolWorkflowResult
from app.tools.tool_dispatcher import (
    ToolDispatchError,
    ToolErrorCode,
    dispatch_tool_call,
)
from app.tools.tool_registry import (
    get_allowed_tool_schemas,
)
from app.workflows.document_workflow_failure import (
    DocumentWorkflowFailure,
    create_document_workflow_failure,
)
from app.workflows.document_workflow_steps import (
    complete_direct_response,
    complete_final_response,
    mark_tool_selected,
    record_tool_observation,
    request_tool_correction,
    retry_tool_execution,
    start_model_decision,
)

TOOL_INSTRUCTIONS = (
    "You are AIRA, a document research assistant. "
    "Use get_document_statistics when the user asks for exact "
    "character, word, or line counts. "
    "Use extract_document_keywords when the user asks for "
    "frequent or representative document keywords. "
    "Do not estimate Tool results yourself. "
    "Choose at most one Tool for the current workflow. "
    "If the user asks for multiple operations that require "
    "different Tools, do not call any Tool. Explain that this "
    "workflow currently supports one Tool operation per request "
    "and ask the user to split the operations into separate requests. "
    "If a Tool result reports invalid arguments, correct the "
    "arguments and call the same Tool once more."
)

FINAL_RESPONSE_INSTRUCTIONS = (
    "A local Tool has already executed successfully. "
    "The function_call_output contains the authoritative "
    "Tool result. "
    "Answer the user using that result. "
    "Do not claim that the Tool is unavailable, that it "
    "cannot be executed, or that the result is approximate. "
    "Do not ask to run the Tool again. "
    "Preserve exact counts, keywords, and other values from "
    "the Tool result."
)


RECOVERABLE_TOOL_ERRORS = {
    ToolErrorCode.INVALID_JSON,
    ToolErrorCode.INVALID_ARGUMENT_CONTAINER,
    ToolErrorCode.ARGUMENT_VALIDATION_FAILED,
}


class ToolCallingErrorCode(StrEnum):
    """Stable error codes for the Tool Calling workflow."""

    INVALID_RESPONSE = "invalid_response"
    MULTIPLE_TOOL_CALLS = "multiple_tool_calls"
    INVALID_FUNCTION_CALL = "invalid_function_call"
    TOOL_CALL_FAILED = "tool_call_failed"
    TOOL_CORRECTION_FAILED = "tool_correction_failed"
    MISSING_FINAL_TEXT = "missing_final_text"


class ToolCallingError(RuntimeError):
    """A classified Tool Calling workflow failure."""

    def __init__(
        self,
        *,
        code: ToolCallingErrorCode,
        safe_message: str,
        failure: DocumentWorkflowFailure | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.failure = failure


def _workflow_error(
    state: DocumentWorkflowState,
    *,
    code: ToolCallingErrorCode,
    safe_message: str,
) -> ToolCallingError:
    """Create a Tool error with a structured FAILED state."""

    failure = create_document_workflow_failure(
        state,
        error_code=code.value,
        safe_message=safe_message,
    )

    return ToolCallingError(
        code=code,
        safe_message=safe_message,
        failure=failure,
    )


def _elapsed_ms(started_ns: int) -> float:
    """Return milliseconds elapsed since the Workflow started."""

    elapsed_ns = time.perf_counter_ns() - started_ns

    return round(elapsed_ns / 1_000_000, 3)


def _get_item_value(item: object, name: str) -> Any:
    """Read a value from an SDK object or dictionary."""

    if isinstance(item, dict):
        return item.get(name)

    return getattr(item, name, None)


def _find_function_calls(response: object) -> list[object]:
    """Return function-call items from a Responses API response."""

    output = getattr(response, "output", None)

    if not isinstance(output, list):
        raise ToolCallingError(
            code=ToolCallingErrorCode.INVALID_RESPONSE,
            safe_message="response output is missing or invalid",
        )

    return [
        item
        for item in output
        if _get_item_value(item, "type") == "function_call"
    ]


def _get_single_function_call(response: object) -> object | None:
    """Return zero or one function call and reject multiple calls."""

    function_calls = _find_function_calls(response)

    if not function_calls:
        return None

    if len(function_calls) != 1:
        raise ToolCallingError(
            code=ToolCallingErrorCode.MULTIPLE_TOOL_CALLS,
            safe_message=(
                "this workflow allows at most one "
                "Tool call per request"
            ),
        )

    return function_calls[0]


def _get_single_function_call_with_state(
    response: object,
    *,
    state: DocumentWorkflowState,
) -> object | None:
    """Return one function call and preserve structural failures."""

    try:
        return _get_single_function_call(response)
    except ToolCallingError as exc:
        raise _workflow_error(
            state,
            code=exc.code,
            safe_message=exc.safe_message,
        ) from exc


def _extract_function_call(
    function_call: object,
) -> tuple[str, str, str]:
    """Extract and validate function call metadata."""

    tool_name = _get_item_value(function_call, "name")
    arguments = _get_item_value(function_call, "arguments")
    call_id = _get_item_value(function_call, "call_id")

    if not isinstance(tool_name, str) or not tool_name:
        raise ToolCallingError(
            code=ToolCallingErrorCode.INVALID_FUNCTION_CALL,
            safe_message="function call name is missing",
        )

    if not isinstance(arguments, str):
        raise ToolCallingError(
            code=ToolCallingErrorCode.INVALID_FUNCTION_CALL,
            safe_message="function call arguments are missing",
        )

    if not isinstance(call_id, str) or not call_id:
        raise ToolCallingError(
            code=ToolCallingErrorCode.INVALID_FUNCTION_CALL,
            safe_message="function call ID is missing",
        )

    return tool_name, arguments, call_id


def _extract_function_call_with_state(
    function_call: object,
    *,
    state: DocumentWorkflowState,
) -> tuple[str, str, str]:
    """Extract function-call metadata and preserve failures."""

    try:
        return _extract_function_call(function_call)
    except ToolCallingError as exc:
        raise _workflow_error(
            state,
            code=exc.code,
            safe_message=exc.safe_message,
        ) from exc


def _execute_function_call(
    function_call: object,
) -> tuple[str, dict[str, Any]]:
    """Execute one validated local function call."""

    tool_name, arguments, call_id = _extract_function_call(
        function_call
    )

    result = dispatch_tool_call(
        tool_name=tool_name,
        arguments_json=arguments,
    )

    return call_id, result


def _tool_output_item(
    *,
    call_id: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    """Build a Responses API function-call output item."""

    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _get_final_text(response: object) -> str:
    """Return non-empty final response text."""

    final_text = getattr(response, "output_text", None)

    if not isinstance(final_text, str) or not final_text.strip():
        raise ToolCallingError(
            code=ToolCallingErrorCode.MISSING_FINAL_TEXT,
            safe_message="final response text is missing",
        )

    return final_text.strip()


def _get_final_text_with_state(
    response: object,
    *,
    state: DocumentWorkflowState,
) -> str:
    """Return final text and preserve missing-text failures."""

    try:
        return _get_final_text(response)
    except ToolCallingError as exc:
        raise _workflow_error(
            state,
            code=exc.code,
            safe_message=exc.safe_message,
        ) from exc


def run_document_tool_workflow(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> ToolWorkflowResult:
    """Run at most one registered document Tool."""


    started_ns = time.perf_counter_ns()

    if not user_request.strip():
        raise ValueError("user_request must not be empty")

    events = [
        ToolWorkflowEvent(
            elapsed_ms=_elapsed_ms(started_ns),
            event_type=ToolWorkflowEventType.REQUEST_RECEIVED,
            details={
                "request_length": len(user_request),
            },
        )
    ]

    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request=user_request,
        events=events,
    )
    state = start_model_decision(state)

    allowed_tools = get_allowed_tool_schemas()

    first_response = client.responses.create(
        model=model,
        instructions=TOOL_INSTRUCTIONS,
        input=user_request,
        tools=allowed_tools,
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    function_call = _get_single_function_call_with_state(
        first_response,
        state=state,
    )

    if function_call is None:
        final_answer = _get_final_text_with_state(
            first_response,
            state=state,
        )

        events.append(
            ToolWorkflowEvent(
                elapsed_ms=_elapsed_ms(started_ns),
                event_type=ToolWorkflowEventType.DIRECT_RESPONSE,
            )
        )

        state = complete_direct_response(
            state,
            final_answer=final_answer,
            events=events,
        )

        return ToolWorkflowResult(
            tool_used=False,
            final_answer=state.final_answer,
            workflow_status=state.status,
            correction_attempted=(
                state.correction_attempted
            ),
            events=state.events,
        )

    tool_name, _, _ = _extract_function_call_with_state(
        function_call,
        state=state,
    )

    events.append(
        ToolWorkflowEvent(
            elapsed_ms=_elapsed_ms(started_ns),
            event_type=ToolWorkflowEventType.TOOL_SELECTED,
            tool_name=tool_name,
        )
    )

    _, arguments_json, call_id = (
        _extract_function_call_with_state(
            function_call,
            state=state,
        )
    )
    state = mark_tool_selected(
        state,
        tool_name=tool_name,
        call_id=call_id,
        arguments_json=arguments_json,
        events=events,
    )

    try:
        call_id, tool_result = _execute_function_call(
            function_call
        )
        events.append(
            ToolWorkflowEvent(
                elapsed_ms=_elapsed_ms(started_ns),
                event_type=(
                    ToolWorkflowEventType.TOOL_EXECUTION_SUCCEEDED
                ),
                tool_name=tool_name,
            )
        )
        state = record_tool_observation(
            state,
            observation=tool_result,
            events=events,
        )
    except ToolDispatchError as exc:
        if exc.code not in RECOVERABLE_TOOL_ERRORS:
            raise _workflow_error(
                state,
                code=ToolCallingErrorCode.TOOL_CALL_FAILED,
                safe_message=exc.safe_message,
            ) from exc

        _, _, failed_call_id = _extract_function_call(
            function_call
        )

        events.append(
            ToolWorkflowEvent(
                elapsed_ms=_elapsed_ms(started_ns),
                event_type=(
                    ToolWorkflowEventType
                    .TOOL_ARGUMENT_CORRECTION_REQUESTED
                ),
                tool_name=tool_name,
                details={
                    "error_code": exc.code.value,
                },
            )
        )
        state = request_tool_correction(
            state,
            events=events,
        )

        correction_response = client.responses.create(
            model=model,
            instructions=TOOL_INSTRUCTIONS,
            previous_response_id=first_response.id,
            input=[
                _tool_output_item(
                    call_id=failed_call_id,
                    payload={
                        "ok": False,
                        "error": {
                            "code": exc.code.value,
                            "message": exc.safe_message,
                        },
                    },
                )
            ],
            tools=allowed_tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )

        corrected_call = (
            _get_single_function_call_with_state(
                correction_response,
                state=state,
            )
        )

        if corrected_call is None:
            raise _workflow_error(
                state,
                code=(
                    ToolCallingErrorCode.TOOL_CORRECTION_FAILED
                ),
                safe_message=(
                    "model did not provide a corrected tool call"
                ),
            )

        tool_name, arguments_json, corrected_call_id = (
            _extract_function_call_with_state(
                corrected_call,
                state=state,
            )
        )
        state = retry_tool_execution(
            state,
            tool_name=tool_name,
            call_id=corrected_call_id,
            arguments_json=arguments_json,
            events=events,
        )

        try:
            call_id, tool_result = _execute_function_call(
                corrected_call
            )
            events.append(
                ToolWorkflowEvent(
                    elapsed_ms=_elapsed_ms(started_ns),
                    event_type=(
                        ToolWorkflowEventType
                        .TOOL_ARGUMENTS_CORRECTED
                    ),
                    tool_name=tool_name,
                )
            )
            events.append(
                ToolWorkflowEvent(
                    elapsed_ms=_elapsed_ms(started_ns),
                    event_type=(
                        ToolWorkflowEventType
                        .TOOL_EXECUTION_SUCCEEDED
                    ),
                    tool_name=tool_name,
                )
            )
            state = record_tool_observation(
                state,
                observation=tool_result,
                events=events,
            )
        except ToolDispatchError as retry_exc:
            raise _workflow_error(
                state,
                code=(
                    ToolCallingErrorCode.TOOL_CORRECTION_FAILED
                ),
                safe_message=(
                    "corrected tool call failed validation "
                    "or execution"
                ),
            ) from retry_exc

        previous_response_id = correction_response.id
    else:
        previous_response_id = first_response.id

    final_response = client.responses.create(
        model=model,
        instructions=(
            f"{TOOL_INSTRUCTIONS} "
            f"{FINAL_RESPONSE_INSTRUCTIONS}"
        ),
        previous_response_id=previous_response_id,
        input=[
            _tool_output_item(
                call_id=call_id,
                payload={
                    "ok": True,
                    "result": tool_result,
                },
            )
        ],
        tools=allowed_tools,
        tool_choice="none",
    )

    final_answer = _get_final_text_with_state(
        final_response,
        state=state,
    )

    events.append(
        ToolWorkflowEvent(
            elapsed_ms=_elapsed_ms(started_ns),
            event_type=ToolWorkflowEventType.FINAL_RESPONSE_CREATED,
        )
    )
    state = complete_final_response(
        state,
        final_answer=final_answer,
        events=events,
    )

    return ToolWorkflowResult(
        tool_used=True,
        tool_name=state.selected_tool_name,
        observation=state.observation,
        final_answer=state.final_answer,
        workflow_status=state.status,
        correction_attempted=state.correction_attempted,
        events=state.events,
    )


def answer_with_document_tools(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> str:
    """Return only the final answer from the document Tool workflow."""

    result = run_document_tool_workflow(
        client=client,
        model=model,
        user_request=user_request,
    )

    return result.final_answer


def run_document_statistics_tool_workflow(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> ToolWorkflowResult:
    """Backward-compatible alias for the generalized workflow."""

    return run_document_tool_workflow(
        client=client,
        model=model,
        user_request=user_request,
    )


def answer_with_document_statistics_tool(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> str:
    """Backward-compatible alias for the generalized answer helper."""

    return answer_with_document_tools(
        client=client,
        model=model,
        user_request=user_request,
    )
