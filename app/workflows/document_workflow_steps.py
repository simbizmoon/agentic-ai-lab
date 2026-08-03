"""Named state-transition steps for the document workflow."""

from __future__ import annotations

from typing import Any

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.schemas.tool_workflow_event import ToolWorkflowEvent
from app.workflows.document_state_machine import (
    transition_document_workflow,
)


def start_model_decision(
    state: DocumentWorkflowState,
) -> DocumentWorkflowState:
    """Move a received workflow to model decision."""

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.MODEL_DECISION,
    )


def complete_direct_response(
    state: DocumentWorkflowState,
    *,
    final_answer: str,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Complete a workflow that did not require a Tool."""

    updates: dict[str, object] = {
        "final_answer": final_answer,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.COMPLETED,
        updates=updates,
    )


def mark_tool_selected(
    state: DocumentWorkflowState,
    *,
    tool_name: str,
    call_id: str,
    arguments_json: str,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Move model decision to Tool execution."""

    updates: dict[str, object] = {
        "selected_tool_name": tool_name,
        "tool_call_id": call_id,
        "tool_arguments_json": arguments_json,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.TOOL_EXECUTION,
        updates=updates,
    )


def request_tool_correction(
    state: DocumentWorkflowState,
    *,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Move failed Tool arguments to correction state."""

    updates: dict[str, object] = {
        "correction_attempted": True,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.TOOL_CORRECTION,
        updates=updates,
    )


def retry_tool_execution(
    state: DocumentWorkflowState,
    *,
    tool_name: str,
    call_id: str,
    arguments_json: str,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Move corrected Tool arguments back to execution."""

    updates: dict[str, object] = {
        "selected_tool_name": tool_name,
        "tool_call_id": call_id,
        "tool_arguments_json": arguments_json,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.TOOL_EXECUTION,
        updates=updates,
    )


def record_tool_observation(
    state: DocumentWorkflowState,
    *,
    observation: dict[str, Any],
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Move successful Tool execution to final response."""

    updates: dict[str, object] = {
        "observation": observation,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.FINAL_RESPONSE,
        updates=updates,
    )


def complete_final_response(
    state: DocumentWorkflowState,
    *,
    final_answer: str,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Complete a workflow after generating the final response."""

    updates: dict[str, object] = {
        "final_answer": final_answer,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.COMPLETED,
        updates=updates,
    )


def fail_document_workflow(
    state: DocumentWorkflowState,
    *,
    error_code: str,
    error_message: str,
    events: list[ToolWorkflowEvent] | None = None,
) -> DocumentWorkflowState:
    """Move a nonterminal workflow to failed state."""

    updates: dict[str, object] = {
        "error_code": error_code,
        "error_message": error_message,
    }

    if events is not None:
        updates["events"] = events

    return transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.FAILED,
        updates=updates,
    )
