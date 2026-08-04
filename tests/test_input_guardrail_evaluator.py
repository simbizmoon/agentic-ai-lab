"""Tests for deterministic input guardrail evaluation."""

import pytest
from pydantic import ValidationError

from app.guardrails.guardrail_result import (
    GuardrailDecision,
)
from app.guardrails.input_guardrail_evaluator import (
    InputGuardrailEvaluator,
)
from app.guardrails.input_guardrail_evaluator_error import (
    InputGuardrailEvaluatorError,
)
from app.guardrails.input_guardrail_snapshot import (
    InputGuardrailSnapshot,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)


def identity(
    *,
    agent_id: str = "agent-search-001",
    role: ResearchAgentRole = (
        ResearchAgentRole.SEARCH_SPECIALIST
    ),
) -> ResearchAgentIdentity:
    """Return one research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager delegation profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )


def assignee_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return one search specialist capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-search-001",
        agent=agent or identity(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.SEARCH_SOURCES,
            ]
        ),
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one executable search assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-search-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "assigner_profile": manager_profile(),
        "assignee": identity(),
        "required_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "required_capabilities": [
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        "title": "Search research sources",
        "objective": "Find authoritative sources.",
        "instructions": [
            "Return normalized source candidates.",
        ],
        "inputs": [
            ResearchAgentAssignmentInput(
                name="research-question",
                reference_type="research_question",
                reference_id="question-001",
            )
        ],
        "expected_output_type": (
            "research_source_candidate_set"
        ),
        "acceptance_criteria": [
            "Return at least one source candidate.",
        ],
        "status": (
            ResearchAgentAssignmentStatus.IN_PROGRESS
        ),
        "attempt_number": 1,
        "maximum_attempts": 2,
    }
    values.update(overrides)

    return ResearchAgentTaskAssignment.model_validate(
        values
    )


def snapshot(
    *,
    assignment_value: ResearchAgentTaskAssignment | None = None,
    profile: ResearchAgentCapabilityProfile | None = None,
    available_reference_ids: list[str] | None = None,
    expected_request_id: str = "research-001",
    expected_workspace_id: str = "workspace-001",
    require_inputs: bool = True,
) -> InputGuardrailSnapshot:
    """Return one valid input guardrail snapshot."""

    return InputGuardrailSnapshot(
        assignment=assignment_value or assignment(),
        assignee_profile=profile or assignee_profile(),
        available_reference_ids=(
            available_reference_ids
            if available_reference_ids is not None
            else ["question-001"]
        ),
        expected_request_id=expected_request_id,
        expected_workspace_id=expected_workspace_id,
        require_inputs=require_inputs,
    )


def evaluator() -> InputGuardrailEvaluator:
    """Return one deterministic input guardrail evaluator."""

    return InputGuardrailEvaluator(
        evaluation_id_factory=(
            lambda: "input-guardrail-evaluation-001"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_valid_assignment_is_allowed() -> None:
    value = evaluator().evaluate(snapshot())

    assert value.decision is GuardrailDecision.ALLOWED
    assert value.allowed is True
    assert value.violations == []
    assert value.blocking_violations == []


def test_assignee_profile_mismatch_is_blocked() -> None:
    other = identity(agent_id="agent-search-002")

    value = evaluator().evaluate(
        snapshot(
            profile=assignee_profile(agent=other)
        )
    )

    assert value.decision is GuardrailDecision.BLOCKED
    assert any(
        violation.code == "ASSIGNEE_PROFILE_MISMATCH"
        for violation in value.violations
    )


def test_assignment_schema_rejects_role_mismatch() -> None:
    wrong_role = identity(
        role=ResearchAgentRole.SOURCE_READER
    )

    with pytest.raises(
        ValidationError,
        match=(
            "assignee role must match required_role"
        ),
    ):
        assignment(
            assignee=wrong_role,
        )


def test_missing_capability_is_blocked() -> None:
    profile = assignee_profile(capabilities=[])

    value = evaluator().evaluate(
        snapshot(profile=profile)
    )

    assert any(
        violation.code == "MISSING_REQUIRED_CAPABILITY"
        for violation in value.violations
    )


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentAssignmentStatus.CREATED,
        ResearchAgentAssignmentStatus.COMPLETED,
        ResearchAgentAssignmentStatus.FAILED,
        ResearchAgentAssignmentStatus.CANCELLED,
    ],
)
def test_nonexecutable_status_is_blocked(
    status: ResearchAgentAssignmentStatus,
) -> None:
    value = evaluator().evaluate(
        snapshot(
            assignment_value=assignment(status=status)
        )
    )

    assert any(
        violation.code
        == "ASSIGNMENT_STATUS_NOT_EXECUTABLE"
        for violation in value.violations
    )


def test_missing_inputs_are_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            assignment_value=assignment(inputs=[]),
            available_reference_ids=[],
        )
    )

    assert any(
        violation.code == "MISSING_ASSIGNMENT_INPUTS"
        for violation in value.violations
    )


def test_input_requirement_can_be_disabled() -> None:
    value = evaluator().evaluate(
        snapshot(
            assignment_value=assignment(inputs=[]),
            available_reference_ids=[],
            require_inputs=False,
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_unavailable_reference_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(available_reference_ids=[])
    )

    assert any(
        violation.code == "INPUT_REFERENCE_NOT_AVAILABLE"
        for violation in value.violations
    )


def test_request_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(expected_request_id="research-other")
    )

    assert any(
        violation.code == "REQUEST_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_workspace_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            expected_workspace_id="workspace-other"
        )
    )

    assert any(
        violation.code == "WORKSPACE_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_multiple_violations_are_preserved() -> None:
    value = evaluator().evaluate(
        snapshot(
            assignment_value=assignment(
                inputs=[],
                status=(
                    ResearchAgentAssignmentStatus.CREATED
                ),
            ),
            profile=assignee_profile(capabilities=[]),
            available_reference_ids=[],
            expected_request_id="research-other",
            expected_workspace_id="workspace-other",
        )
    )

    codes = {
        violation.code
        for violation in value.violations
    }

    assert "MISSING_REQUIRED_CAPABILITY" in codes
    assert "ASSIGNMENT_STATUS_NOT_EXECUTABLE" in codes
    assert "MISSING_ASSIGNMENT_INPUTS" in codes
    assert "REQUEST_CONTEXT_MISMATCH" in codes
    assert "WORKSPACE_CONTEXT_MISMATCH" in codes


def test_snapshot_rejects_duplicate_reference_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "available_reference_ids must not contain "
            "duplicates"
        ),
    ):
        snapshot(
            available_reference_ids=[
                "Question-001",
                "question-001",
            ]
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = InputGuardrailEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        InputGuardrailEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(snapshot())
