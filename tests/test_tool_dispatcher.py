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


def test_dispatcher_uses_registered_tool_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tools import tool_dispatcher

    class FakeInput:
        @classmethod
        def model_validate(
            cls,
            raw_arguments: object,
        ) -> object:
            assert raw_arguments == {"value": "input"}
            return object()

    class FakeResult:
        def model_dump(
            self,
            *,
            mode: str,
        ) -> dict[str, object]:
            assert mode == "json"
            return {"value": "output"}

    class FakeDefinition:
        input_model = FakeInput
        requires_approval = False

        @staticmethod
        def executor(tool_input: object) -> FakeResult:
            assert tool_input is not None
            return FakeResult()

    monkeypatch.setattr(
        tool_dispatcher,
        "get_allowed_tool",
        lambda tool_name: (
            FakeDefinition()
            if tool_name == "registered_tool"
            else None
        ),
    )
    monkeypatch.setattr(
        tool_dispatcher,
        "BaseModel",
        FakeResult,
    )

    result = tool_dispatcher.dispatch_tool_call(
        tool_name="registered_tool",
        arguments_json='{"value":"input"}',
    )

    assert result == {"value": "output"}


def test_dispatcher_blocks_tool_without_required_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import BaseModel, ConfigDict

    from app.tools import tool_dispatcher

    class DangerousInput(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

        target: str

    class DangerousOutput(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

        completed: bool

    class DangerousDefinition:
        input_model = DangerousInput
        requires_approval = True

        @staticmethod
        def executor(tool_input: BaseModel) -> BaseModel:
            return DangerousOutput(completed=True)

    monkeypatch.setattr(
        tool_dispatcher,
        "get_allowed_tool",
        lambda tool_name: (
            DangerousDefinition()
            if tool_name == "dangerous_tool"
            else None
        ),
    )

    with pytest.raises(ToolDispatchError) as exc_info:
        tool_dispatcher.dispatch_tool_call(
            tool_name="dangerous_tool",
            arguments_json='{"target":"production"}',
        )

    assert (
        exc_info.value.code
        == ToolErrorCode.APPROVAL_REQUIRED
    )
    assert exc_info.value.safe_message == (
        "human approval is required for tool: dangerous_tool"
    )


def test_dispatcher_executes_tool_after_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import BaseModel, ConfigDict

    from app.tools import tool_dispatcher

    class ApprovedInput(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

        target: str

    class ApprovedOutput(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

        target: str
        completed: bool

    class ApprovedDefinition:
        input_model = ApprovedInput
        requires_approval = True

        @staticmethod
        def executor(tool_input: BaseModel) -> BaseModel:
            validated = ApprovedInput.model_validate(tool_input)

            return ApprovedOutput(
                target=validated.target,
                completed=True,
            )

    monkeypatch.setattr(
        tool_dispatcher,
        "get_allowed_tool",
        lambda tool_name: (
            ApprovedDefinition()
            if tool_name == "approved_tool"
            else None
        ),
    )

    result = tool_dispatcher.dispatch_tool_call(
        tool_name="approved_tool",
        arguments_json='{"target":"staging"}',
        approval_granted=True,
    )

    assert result == {
        "target": "staging",
        "completed": True,
    }


def test_read_only_tool_does_not_require_approval() -> None:
    result = dispatch_tool_call(
        tool_name="get_document_statistics",
        arguments_json='{"document_text":"safe text"}',
    )

    assert result == {
        "character_count": 9,
        "word_count": 2,
        "line_count": 1,
    }
