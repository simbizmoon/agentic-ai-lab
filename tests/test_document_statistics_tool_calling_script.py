"""Tests for the document statistics Tool Calling CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services.document_statistics_tool_calling import (
    ToolCallingError,
    ToolCallingErrorCode,
)
from scripts import document_statistics_tool_calling as script


def test_exit_code_for_tool_call_failed() -> None:
    error = ToolCallingError(
        code=ToolCallingErrorCode.TOOL_CALL_FAILED,
        safe_message="unsupported tool",
    )

    assert script.exit_code_for_tool_error(error) == 3


def test_exit_code_for_tool_correction_failed() -> None:
    error = ToolCallingError(
        code=ToolCallingErrorCode.TOOL_CORRECTION_FAILED,
        safe_message="correction failed",
    )

    assert script.exit_code_for_tool_error(error) == 3


def test_exit_code_for_invalid_response() -> None:
    error = ToolCallingError(
        code=ToolCallingErrorCode.INVALID_RESPONSE,
        safe_message="invalid response",
    )

    assert script.exit_code_for_tool_error(error) == 4


def test_main_rejects_empty_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = tmp_path / "empty.txt"
    document.write_text("   \n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["document_statistics_tool_calling.py", str(document)],
    )

    exit_code = script.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "non-whitespace text" in captured.err


def test_main_returns_tool_error_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = tmp_path / "document.txt"
    document.write_text("valid text", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["document_statistics_tool_calling.py", str(document)],
    )
    monkeypatch.setattr(
        script,
        "load_settings",
        lambda: type(
            "FakeSettings",
            (),
            {"openai_model": "test-model"},
        )(),
    )
    monkeypatch.setattr(
        script,
        "create_openai_client",
        lambda settings: object(),
    )

    def fail_tool_workflow(**kwargs: object) -> str:
        raise ToolCallingError(
            code=ToolCallingErrorCode.TOOL_CALL_FAILED,
            safe_message="unsupported tool: dangerous_tool",
        )

    monkeypatch.setattr(
        script,
        "run_document_tool_workflow",
        fail_tool_workflow,
    )

    exit_code = script.main()
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "[tool_call_failed]" in captured.err
    assert "unsupported tool: dangerous_tool" in captured.err


def test_main_prints_observation_and_final_answer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    document = tmp_path / "document.txt"
    document.write_text("valid text", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["document_statistics_tool_calling.py", str(document)],
    )
    monkeypatch.setattr(
        script,
        "load_settings",
        lambda: SimpleNamespace(openai_model="test-model"),
    )
    monkeypatch.setattr(
        script,
        "create_openai_client",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        script,
        "run_document_tool_workflow",
        lambda **kwargs: SimpleNamespace(
            tool_used=True,
            tool_name="get_document_statistics",
            observation={
                "character_count": 10,
                "word_count": 2,
                "line_count": 1,
            },
            final_answer=(
                "The document has 10 characters, "
                "2 words, and 1 line."
            ),
        ),
    )

    exit_code = script.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Observation:" in captured.out
    assert "get_document_statistics" in captured.out
    assert "character_count: 10" in captured.out
    assert "word_count: 2" in captured.out
    assert "line_count: 1" in captured.out
    assert "Final Answer:" in captured.out
    assert "The document has 10 characters" in captured.out
