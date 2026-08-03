"""Tests for the generalized document Tool CLI."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from app.schemas.tool_workflow_event import (
    ToolWorkflowEvent,
    ToolWorkflowEventType,
)
from app.schemas.tool_workflow_result import ToolWorkflowResult
from scripts import document_tool_calling as script


def test_main_prints_events_when_requested(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    document_path = tmp_path / "document.txt"
    document_path.write_text(
        "agent tool agent",
        encoding="utf-8",
    )

    result = ToolWorkflowResult(
        tool_used=True,
        tool_name="extract_document_keywords",
        observation={
            "keywords": [
                {
                    "keyword": "agent",
                    "count": 2,
                }
            ]
        },
        final_answer="agent appears twice.",
        events=[
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.REQUEST_RECEIVED
                ),
                details={"request_length": 50},
            ),
            ToolWorkflowEvent(
                event_type=ToolWorkflowEventType.TOOL_SELECTED,
                tool_name="extract_document_keywords",
            ),
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType
                    .TOOL_EXECUTION_SUCCEEDED
                ),
                tool_name="extract_document_keywords",
            ),
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.FINAL_RESPONSE_CREATED
                ),
            ),
        ],
    )

    monkeypatch.setattr(
        script,
        "load_settings",
        lambda: SimpleNamespace(
            openai_model="test-model",
        ),
    )
    monkeypatch.setattr(
        script,
        "create_openai_client",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        script,
        "run_document_tool_workflow",
        lambda **kwargs: result,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "document_tool_calling.py",
            str(document_path),
            "--request",
            "Extract keywords.",
            "--show-events",
        ],
    )

    exit_code = script.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Events:" in captured.out
    assert "1. request_received" in captured.out
    assert (
        "2. tool_selected [extract_document_keywords]"
        in captured.out
    )
    assert (
        "3. tool_execution_succeeded "
        "[extract_document_keywords]"
        in captured.out
    )
    assert "4. final_response_created" in captured.out
    assert "Observation:" in captured.out
    assert "Final Answer:" in captured.out


def test_main_hides_events_by_default(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    document_path = tmp_path / "document.txt"
    document_path.write_text(
        "plain document",
        encoding="utf-8",
    )

    result = ToolWorkflowResult(
        tool_used=False,
        final_answer="No Tool was required.",
        events=[
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.REQUEST_RECEIVED
                ),
            ),
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.DIRECT_RESPONSE
                ),
            ),
        ],
    )

    monkeypatch.setattr(
        script,
        "load_settings",
        lambda: SimpleNamespace(
            openai_model="test-model",
        ),
    )
    monkeypatch.setattr(
        script,
        "create_openai_client",
        lambda settings: object(),
    )
    monkeypatch.setattr(
        script,
        "run_document_tool_workflow",
        lambda **kwargs: result,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "document_tool_calling.py",
            str(document_path),
            "--request",
            "Explain this document.",
        ],
    )

    exit_code = script.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Events:" not in captured.out
    assert "Observation:" not in captured.out
    assert "Final Answer:" in captured.out
    assert "No Tool was required." in captured.out
