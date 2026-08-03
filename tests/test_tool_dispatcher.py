"""Tests for local tool dispatching."""

import json

import pytest

from app.tools.tool_dispatcher import (
    ToolDispatchError,
    ToolErrorCode,
    dispatch_tool_call,
)


def test_dispatch_document_statistics_tool() -> None:
    result = dispatch_tool_call(
        tool_name="get_document_statistics",
        arguments_json=json.dumps(
            {
                "document_text": (
                    "Agent tools are useful.\n"
                    "They execute code."
                )
            }
        ),
    )

    assert result == {
        "character_count": 42,
        "word_count": 7,
        "line_count": 2,
    }


def test_dispatch_rejects_unknown_tool() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="delete_all_files",
            arguments_json="{}",
        )

    error = exc_info.value

    assert error.code == ToolErrorCode.UNSUPPORTED_TOOL
    assert error.safe_message == (
        "unsupported tool: delete_all_files"
    )


def test_dispatch_rejects_invalid_json() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="get_document_statistics",
            arguments_json="{invalid",
        )

    error = exc_info.value

    assert error.code == ToolErrorCode.INVALID_JSON
    assert error.safe_message == (
        "tool arguments are not valid JSON"
    )
    assert isinstance(error.__cause__, json.JSONDecodeError)


def test_dispatch_rejects_non_object_arguments() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="get_document_statistics",
            arguments_json='["text"]',
        )

    error = exc_info.value

    assert (
        error.code
        == ToolErrorCode.INVALID_ARGUMENT_CONTAINER
    )
    assert error.safe_message == (
        "tool arguments must be a JSON object"
    )


def test_dispatch_rejects_missing_document_text() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="get_document_statistics",
            arguments_json="{}",
        )

    error = exc_info.value

    assert (
        error.code
        == ToolErrorCode.ARGUMENT_VALIDATION_FAILED
    )
    assert error.safe_message == (
        "tool arguments failed validation"
    )


def test_dispatch_rejects_whitespace_only_text() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="get_document_statistics",
            arguments_json=json.dumps(
                {"document_text": " \n\t "}
            ),
        )

    assert (
        exc_info.value.code
        == ToolErrorCode.ARGUMENT_VALIDATION_FAILED
    )


def test_dispatch_rejects_extra_arguments() -> None:
    with pytest.raises(ToolDispatchError) as exc_info:
        dispatch_tool_call(
            tool_name="get_document_statistics",
            arguments_json=json.dumps(
                {
                    "document_text": "valid text",
                    "unsupported": True,
                }
            ),
        )

    assert (
        exc_info.value.code
        == ToolErrorCode.ARGUMENT_VALIDATION_FAILED
    )
