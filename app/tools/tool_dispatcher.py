"""Dispatch validated local tool calls."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from app.tools.document_statistics import (
    DocumentStatisticsInput,
    get_document_statistics,
)


class ToolErrorCode(StrEnum):
    """Stable error codes produced by local tool dispatching."""

    UNSUPPORTED_TOOL = "unsupported_tool"
    INVALID_JSON = "invalid_json"
    INVALID_ARGUMENT_CONTAINER = "invalid_argument_container"
    ARGUMENT_VALIDATION_FAILED = "argument_validation_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"


class ToolDispatchError(RuntimeError):
    """A safe, classified local tool dispatch failure."""

    def __init__(
        self,
        *,
        code: ToolErrorCode,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def dispatch_tool_call(
    *,
    tool_name: str,
    arguments_json: str,
) -> dict[str, Any]:
    """Validate and execute an allowed local tool call."""

    if tool_name != "get_document_statistics":
        raise ToolDispatchError(
            code=ToolErrorCode.UNSUPPORTED_TOOL,
            safe_message=f"unsupported tool: {tool_name}",
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
        tool_input = DocumentStatisticsInput.model_validate(
            raw_arguments
        )
    except ValidationError as exc:
        raise ToolDispatchError(
            code=ToolErrorCode.ARGUMENT_VALIDATION_FAILED,
            safe_message="tool arguments failed validation",
        ) from exc

    try:
        result = get_document_statistics(tool_input)
    except Exception as exc:
        raise ToolDispatchError(
            code=ToolErrorCode.TOOL_EXECUTION_FAILED,
            safe_message="local tool execution failed",
        ) from exc

    return result.model_dump()
