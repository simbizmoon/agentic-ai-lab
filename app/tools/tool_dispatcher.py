"""Dispatch explicitly allowed and validated local Tool calls."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError

from app.tools.tool_registry import get_allowed_tool


class ToolErrorCode(StrEnum):
    """Stable error codes produced by local Tool dispatching."""

    UNSUPPORTED_TOOL = "unsupported_tool"
    APPROVAL_REQUIRED = "approval_required"
    INVALID_JSON = "invalid_json"
    INVALID_ARGUMENT_CONTAINER = "invalid_argument_container"
    ARGUMENT_VALIDATION_FAILED = "argument_validation_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"


class ToolDispatchError(RuntimeError):
    """A safe, classified local Tool dispatch failure."""

    def __init__(
        self,
        *,
        code: ToolErrorCode,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def _serialize_tool_result(
    result: BaseModel,
) -> dict[str, Any]:
    """Convert a validated Tool result to a JSON-compatible dictionary."""

    return result.model_dump(mode="json")


def dispatch_tool_call(
    *,
    tool_name: str,
    arguments_json: str,
    approval_granted: bool = False,
) -> dict[str, Any]:
    """Validate and execute one explicitly allowed local Tool call."""

    definition = get_allowed_tool(tool_name)

    if definition is None:
        raise ToolDispatchError(
            code=ToolErrorCode.UNSUPPORTED_TOOL,
            safe_message=f"unsupported tool: {tool_name}",
        )

    if definition.requires_approval and not approval_granted:
        raise ToolDispatchError(
            code=ToolErrorCode.APPROVAL_REQUIRED,
            safe_message=(
                f"human approval is required for tool: {tool_name}"
            ),
        )

    try:
        raw_arguments = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        raise ToolDispatchError(
            code=ToolErrorCode.INVALID_JSON,
            safe_message="tool arguments are not valid JSON",
        ) from exc

    if not isinstance(raw_arguments, dict):
        raise ToolDispatchError(
            code=ToolErrorCode.INVALID_ARGUMENT_CONTAINER,
            safe_message="tool arguments must be a JSON object",
        )

    try:
        tool_input = definition.input_model.model_validate(
            raw_arguments
        )
    except ValidationError as exc:
        raise ToolDispatchError(
            code=ToolErrorCode.ARGUMENT_VALIDATION_FAILED,
            safe_message="tool arguments failed validation",
        ) from exc

    try:
        result = definition.executor(tool_input)
    except Exception as exc:
        raise ToolDispatchError(
            code=ToolErrorCode.TOOL_EXECUTION_FAILED,
            safe_message="local tool execution failed",
        ) from exc

    if not isinstance(result, BaseModel):
        raise ToolDispatchError(
            code=ToolErrorCode.TOOL_EXECUTION_FAILED,
            safe_message=(
                "local tool returned an unsupported result type"
            ),
        )

    return _serialize_tool_result(result)
