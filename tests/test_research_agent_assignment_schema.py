"""Tests for research-agent task assignment schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentPriority,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
    ResearchWorkspacePermission,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
) -> ResearchAgentIdentity:
    """Return one valid research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager delegation profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
            ResearchAgentCapability.DECOMPOSE_TASKS,
        ],
        workspace_permissions=[
            ResearchWorkspacePermission.READ_REQUEST,
            ResearchWorkspacePermission.READ_TASKS,
            ResearchWorkspacePermission.WRITE_TASKS,
        ],
        allowed_tools=[],
        denied_tools=[],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentRole.SOURCE_CRITIC,
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentRole.CITATION_VERIFIER,
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentRole.QUALITY_REVIEWER,
        ],
    )


def search_agent() -> ResearchAgentIdentity:
    """Return one search specialist identity."""

    return identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def assignment_input(
    **overrides: object,
) -> ResearchAgentAssignmentInput:
    """Return one assignment input reference."""

    values: dict[str, object] = {
        "name": "search-query-set",
        "reference_type": "research_search_query_set",
        "reference_id": "query-set-001",
        "required": True,
        "metadata": {
            "scope": "workspace",
        },
    }
    values.update(overrides)

    return ResearchAgentAssignmentInput.model_validate(
        values
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one valid agent task assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "research_task_id": "task-001",
        "assigner_profile": manager_profile(),
        "assignee": search_agent(),
        "required_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "required_capabilities": [
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        "title": "Find agent-memory sources",
        "objective": (
            "Find authoritative sources about "
            "agent-memory architectures."
        ),
        "instructions": [
            "Use the provided query set.",
            "Prefer primary and official sources.",
        ],
        "inputs": [
            assignment_input(),
        ],
        "expected_output_type": (
            "research_source_candidate_set"
        ),
        "acceptance_criteria": [
            "Return at least one source candidate.",
            "Every candidate must reference a query.",
        ],
        "payload": {
            "maximum_sources": 5,
        },
        "priority": (
            ResearchAgentAssignmentPriority.NORMAL
        ),
        "status": (
            ResearchAgentAssignmentStatus.CREATED
        ),
        "attempt_number": 1,
        "maximum_attempts": 2,
        "created_at": datetime(
            2026,
            8,
            4,
            4,
            30,
            tzinfo=UTC,
        ),
        "metadata": {
            "origin": "manager",
        },
    }
    values.update(overrides)

    return ResearchAgentTaskAssignment.model_validate(
        values
    )


def test_assignment_input_accepts_valid_values() -> None:
    value = assignment_input()

    assert value.reference_id == "query-set-001"
    assert value.required is True


@pytest.mark.parametrize(
    "field_name",
    [
        "name",
        "reference_type",
        "reference_id",
    ],
)
def test_assignment_input_rejects_blank_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        assignment_input(**{field_name: " "})


def test_assignment_accepts_valid_values() -> None:
    value = assignment()

    assert value.assignment_id == "assignment-001"
    assert value.assignee.role is (
        ResearchAgentRole.SEARCH_SPECIALIST
    )
    assert value.is_terminal is False
    assert value.can_retry is False


@pytest.mark.parametrize(
    "field_name",
    [
        "assignment_id",
        "request_id",
        "workspace_id",
        "title",
        "objective",
        "expected_output_type",
    ],
)
def test_assignment_rejects_blank_required_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        assignment(**{field_name: " "})


def test_assignment_rejects_same_assigner_and_assignee() -> None:
    manager = manager_profile()

    with pytest.raises(
        ValidationError,
        match=(
            "assigner and assignee must be different agents"
        ),
    ):
        assignment(assignee=manager.agent)


def test_assignment_rejects_wrong_assignee_role() -> None:
    reader = identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "assignee role must match required_role"
        ),
    ):
        assignment(assignee=reader)


def test_assignment_rejects_unauthorized_delegation() -> None:
    restricted_profile = manager_profile().model_copy(
        update={
            "delegatable_roles": [
                ResearchAgentRole.SOURCE_READER,
            ],
        }
    )

    with pytest.raises(
        ValidationError,
        match=(
            "assigner is not permitted to delegate "
            "to required_role"
        ),
    ):
        assignment(
            assigner_profile=restricted_profile
        )


def test_assignment_rejects_duplicate_capabilities() -> None:
    capability = (
        ResearchAgentCapability.SEARCH_SOURCES
    )

    with pytest.raises(
        ValidationError,
        match=(
            "required_capabilities must not "
            "contain duplicates"
        ),
    ):
        assignment(
            required_capabilities=[
                capability,
                capability,
            ]
        )


def test_assignment_rejects_blank_instruction() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "instructions must not contain blank values"
        ),
    ):
        assignment(
            instructions=[
                "Use queries.",
                " ",
            ]
        )


def test_assignment_rejects_duplicate_instructions() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "instructions must not contain duplicates"
        ),
    ):
        assignment(
            instructions=[
                "Use queries.",
                " USE QUERIES. ",
            ]
        )


def test_assignment_rejects_duplicate_inputs() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "assignment inputs must not contain "
            "duplicate references"
        ),
    ):
        assignment(
            inputs=[
                assignment_input(),
                assignment_input(
                    name="same-reference",
                ),
            ]
        )


def test_assignment_rejects_attempt_over_limit() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "attempt_number must not exceed "
            "maximum_attempts"
        ),
    ):
        assignment(
            attempt_number=3,
            maximum_attempts=2,
        )


def test_failed_assignment_can_retry() -> None:
    value = assignment(
        status=ResearchAgentAssignmentStatus.FAILED,
        attempt_number=1,
        maximum_attempts=2,
    )

    assert value.is_terminal is True
    assert value.can_retry is True


def test_failed_assignment_at_limit_cannot_retry() -> None:
    value = assignment(
        status=ResearchAgentAssignmentStatus.FAILED,
        attempt_number=2,
        maximum_attempts=2,
    )

    assert value.can_retry is False


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentAssignmentStatus.COMPLETED,
        ResearchAgentAssignmentStatus.FAILED,
        ResearchAgentAssignmentStatus.REJECTED,
        ResearchAgentAssignmentStatus.CANCELLED,
    ],
)
def test_assignment_reports_terminal_status(
    status: ResearchAgentAssignmentStatus,
) -> None:
    value = assignment(status=status)

    assert value.is_terminal is True


def test_assignment_checks_required_capability() -> None:
    value = assignment()

    assert value.requires_capability(
        ResearchAgentCapability.SEARCH_SOURCES
    )
    assert not value.requires_capability(
        ResearchAgentCapability.READ_SOURCES
    )


def test_assignment_returns_input_by_name() -> None:
    value = assignment()

    result = value.input_by_name(
        " SEARCH-QUERY-SET "
    )

    assert result is not None
    assert result.reference_id == "query-set-001"
    assert value.input_by_name("missing") is None


def test_assignment_rejects_blank_input_lookup() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        assignment().input_by_name(" ")


def test_assignment_is_frozen() -> None:
    value = assignment()

    with pytest.raises(ValidationError):
        value.title = "Changed"
