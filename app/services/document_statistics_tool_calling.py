"""Single-tool Responses API workflow for document statistics."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from app.schemas.tool_workflow_result import ToolWorkflowResult
from app.tools.document_statistics_schema import (
    DOCUMENT_STATISTICS_TOOL,
)
from app.tools.tool_dispatcher import (
    ToolDispatchError,
    ToolErrorCode,
    dispatch_tool_call,
)

TOOL_INSTRUCTIONS = (
    "You are AIRA, a document research assistant. "
    "Use get_document_statistics when the user asks for exact "
    "character, word, or line counts. "
    "Do not estimate these counts yourself. "
    "If a tool result reports invalid arguments, correct the "
    "arguments and call the same tool once more."
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
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


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
                "exactly one function call is allowed "
                "in Lesson 4.2"
            ),
        )

    return function_calls[0]


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


def run_document_statistics_tool_workflow(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> ToolWorkflowResult:
    """Run one local tool and preserve its Observation."""

    if not user_request.strip():
        raise ValueError("user_request must not be empty")

    first_response = client.responses.create(
        model=model,
        instructions=TOOL_INSTRUCTIONS,
        input=user_request,
        tools=[DOCUMENT_STATISTICS_TOOL],
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    function_call = _get_single_function_call(first_response)

    if function_call is None:
        return ToolWorkflowResult(
            tool_used=False,
            final_answer=_get_final_text(first_response),
        )

    tool_name, _, _ = _extract_function_call(function_call)

    try:
        call_id, tool_result = _execute_function_call(
            function_call
        )
    except ToolDispatchError as exc:
        if exc.code not in RECOVERABLE_TOOL_ERRORS:
            raise ToolCallingError(
                code=ToolCallingErrorCode.TOOL_CALL_FAILED,
                safe_message=exc.safe_message,
            ) from exc

        _, _, failed_call_id = _extract_function_call(
            function_call
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
            tools=[DOCUMENT_STATISTICS_TOOL],
            tool_choice="auto",
            parallel_tool_calls=False,
        )

        corrected_call = _get_single_function_call(
            correction_response
        )

        if corrected_call is None:
            raise ToolCallingError(
                code=(
                    ToolCallingErrorCode.TOOL_CORRECTION_FAILED
                ),
                safe_message=(
                    "model did not provide a corrected tool call"
                ),
            )

        tool_name, _, _ = _extract_function_call(
            corrected_call
        )

        try:
            call_id, tool_result = _execute_function_call(
                corrected_call
            )
        except ToolDispatchError as retry_exc:
            raise ToolCallingError(
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
        instructions=TOOL_INSTRUCTIONS,
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
        tools=[DOCUMENT_STATISTICS_TOOL],
        tool_choice="none",
    )

    return ToolWorkflowResult(
        tool_used=True,
        tool_name=tool_name,
        observation=tool_result,
        final_answer=_get_final_text(final_response),
    )


def answer_with_document_statistics_tool(
    *,
    client: Any,
    model: str,
    user_request: str,
) -> str:
    """Return only the final answer for backward compatibility."""

    result = run_document_statistics_tool_workflow(
        client=client,
        model=model,
        user_request=user_request,
    )

    return result.final_answer
