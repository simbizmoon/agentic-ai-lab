"""Tests for the multi-agent shared research workspace."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessage,
    ResearchAgentMessageStatus,
    ResearchAgentMessageType,
)
from app.schemas.research_agent_result import (
    ResearchAgentExecutionMetrics,
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)
from app.schemas.research_workspace import ResearchWorkspace
from app.schemas.shared_research_workspace import (
    SharedResearchWorkspace,
    SharedResearchWorkspaceStatus,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
) -> ResearchAgentIdentity:
    """Return one valid research agent."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager() -> ResearchAgentIdentity:
    """Return one manager agent."""

    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def search_agent() -> ResearchAgentIdentity:
    """Return one search specialist."""

    return identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )


def research_workspace() -> ResearchWorkspace:
    """Return one valid Phase 9 research workspace."""

    request = ResearchRequest(
        request_id="research-001",
        question="How does agent memory work?",
        objective="Explain agent memory.",
    )

    graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="research-001",
                title="Agent memory",
                question="How does agent memory work?",
                objective="Produce verified findings.",
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Structured findings.",
            )
        ],
    )

    return ResearchWorkspace(
        workspace_id="workspace-001",
        request=request,
        task_graph=graph,
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one valid assignment."""

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
        "title": "Search sources",
        "objective": "Find authoritative sources.",
        "instructions": [
            "Use the approved query set."
        ],
        "expected_output_type": (
            "research_source_candidate_set"
        ),
        "acceptance_criteria": [
            "Return at least one source."
        ],
        "status": (
            ResearchAgentAssignmentStatus.IN_PROGRESS
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
    }
    values.update(overrides)

    return ResearchAgentTaskAssignment.model_validate(
        values
    )


def result(
    *,
    assignment_value: ResearchAgentTaskAssignment | None = None,
) -> ResearchAgentTaskResult:
    """Return one successful assignment result."""

    value = assignment_value or assignment(
        status=ResearchAgentAssignmentStatus.COMPLETED
    )

    output = ResearchAgentOutputReference(
        name="source-candidates",
        output_type="research_source_candidate_set",
        reference_id="candidate-set-001",
        primary=True,
    )

    return ResearchAgentTaskResult(
        result_id="result-001",
        assignment=value,
        agent=search_agent(),
        status=ResearchAgentResultStatus.SUCCEEDED,
        summary="Found one source.",
        outputs=[output],
        metrics=ResearchAgentExecutionMetrics(
            source_count=1
        ),
        completed_at=datetime(
            2026,
            8,
            4,
            4,
            31,
            tzinfo=UTC,
        ),
    )


def message(
    **overrides: object,
) -> ResearchAgentMessage:
    """Return one direct assignment message."""

    values: dict[str, object] = {
        "message_id": "message-001",
        "message_type": (
            ResearchAgentMessageType.TASK_REQUEST
        ),
        "sender": manager(),
        "recipient": search_agent(),
        "broadcast": False,
        "correlation_id": "correlation-001",
        "assignment_id": "assignment-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "subject": "Search sources",
        "payload": {
            "task_id": "task-001",
        },
        "status": ResearchAgentMessageStatus.CREATED,
        "created_at": datetime(
            2026,
            8,
            4,
            4,
            30,
            tzinfo=UTC,
        ),
    }
    values.update(overrides)

    return ResearchAgentMessage.model_validate(
        values
    )


def shared_workspace(
    **overrides: object,
) -> SharedResearchWorkspace:
    """Return one valid shared research workspace."""

    assignment_value = assignment()

    values: dict[str, object] = {
        "shared_workspace_id": "shared-workspace-001",
        "research_workspace": research_workspace(),
        "status": SharedResearchWorkspaceStatus.IN_PROGRESS,
        "agents": [
            manager(),
            search_agent(),
        ],
        "assignments": [assignment_value],
        "results": [],
        "messages": [message()],
        "active_assignment_ids": [
            "assignment-001"
        ],
        "revision_count": 0,
        "maximum_revisions": 2,
        "metadata": {
            "mode": "multi-agent",
        },
    }
    values.update(overrides)

    return SharedResearchWorkspace.model_validate(
        values
    )


def test_shared_workspace_accepts_valid_values() -> None:
    value = shared_workspace()

    assert value.request_id == "research-001"
    assert value.workspace_id == "workspace-001"
    assert value.is_terminal is False
    assert value.can_revise is True


def test_shared_workspace_rejects_blank_id() -> None:
    with pytest.raises(
        ValidationError,
        match="shared_workspace_id must not be blank",
    ):
        shared_workspace(shared_workspace_id=" ")


def test_shared_workspace_rejects_duplicate_agents() -> None:
    with pytest.raises(
        ValidationError,
        match="agent IDs must be unique",
    ):
        shared_workspace(
            agents=[
                manager(),
                manager(),
            ]
        )


def test_shared_workspace_rejects_assignment_request_mismatch() -> None:
    wrong_assignment = assignment(
        request_id="research-002"
    )

    with pytest.raises(
        ValidationError,
        match=(
            "assignment request_id must match "
            "research workspace"
        ),
    ):
        shared_workspace(
            assignments=[wrong_assignment],
            active_assignment_ids=[
                "assignment-001"
            ],
        )


def test_shared_workspace_rejects_unregistered_assignee() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "assignment assignee must be "
            "a registered agent"
        ),
    ):
        shared_workspace(
            agents=[manager()],
        )


def test_shared_workspace_accepts_registered_result() -> None:
    completed_assignment = assignment(
        status=ResearchAgentAssignmentStatus.COMPLETED
    )

    value = shared_workspace(
        status=SharedResearchWorkspaceStatus.REVIEWING,
        assignments=[completed_assignment],
        results=[
            result(
                assignment_value=completed_assignment
            )
        ],
        active_assignment_ids=[],
    )

    assert len(value.results) == 1


def test_shared_workspace_rejects_result_without_assignment() -> None:
    completed_assignment = assignment(
        assignment_id="assignment-002",
        status=ResearchAgentAssignmentStatus.COMPLETED,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "result must reference a registered assignment"
        ),
    ):
        shared_workspace(
            results=[
                result(
                    assignment_value=completed_assignment
                )
            ]
        )


def test_shared_workspace_rejects_unregistered_message_sender() -> None:
    outsider = identity(
        agent_id="agent-outsider-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Outsider",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "message sender must be a registered agent"
        ),
    ):
        shared_workspace(
            messages=[
                message(sender=outsider)
            ]
        )


def test_shared_workspace_rejects_message_workspace_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "message workspace_id must match "
            "research workspace"
        ),
    ):
        shared_workspace(
            messages=[
                message(
                    workspace_id="workspace-002"
                )
            ]
        )


def test_shared_workspace_rejects_unknown_active_assignment() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "active assignment must reference "
            "a registered assignment"
        ),
    ):
        shared_workspace(
            active_assignment_ids=[
                "missing-assignment"
            ]
        )


def test_shared_workspace_rejects_terminal_active_assignment() -> None:
    completed_assignment = assignment(
        status=ResearchAgentAssignmentStatus.COMPLETED
    )

    with pytest.raises(
        ValidationError,
        match=(
            "terminal assignment must not be active"
        ),
    ):
        shared_workspace(
            assignments=[completed_assignment],
            active_assignment_ids=[
                "assignment-001"
            ],
        )


def test_shared_workspace_rejects_revision_over_limit() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "revision_count must not exceed "
            "maximum_revisions"
        ),
    ):
        shared_workspace(
            revision_count=3,
            maximum_revisions=2,
        )


def test_revising_workspace_requires_revision_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "revising workspace must have "
            "positive revision_count"
        ),
    ):
        shared_workspace(
            status=SharedResearchWorkspaceStatus.REVISING,
            revision_count=0,
        )


def test_completed_workspace_rejects_active_assignments() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "completed workspace must not have "
            "active assignments"
        ),
    ):
        shared_workspace(
            status=SharedResearchWorkspaceStatus.COMPLETED
        )


def test_shared_workspace_returns_agent() -> None:
    value = shared_workspace()

    found = value.agent(" AGENT-SEARCH-001 ")

    assert found is not None
    assert found.role is (
        ResearchAgentRole.SEARCH_SPECIALIST
    )
    assert value.agent("missing") is None


def test_shared_workspace_returns_assignment() -> None:
    value = shared_workspace()

    found = value.assignment(
        " ASSIGNMENT-001 "
    )

    assert found is not None
    assert found.title == "Search sources"


def test_shared_workspace_returns_results_for_assignment() -> None:
    completed_assignment = assignment(
        status=ResearchAgentAssignmentStatus.COMPLETED
    )

    value = shared_workspace(
        status=SharedResearchWorkspaceStatus.REVIEWING,
        assignments=[completed_assignment],
        results=[
            result(
                assignment_value=completed_assignment
            )
        ],
        active_assignment_ids=[],
    )

    assert len(
        value.results_for_assignment(
            " ASSIGNMENT-001 "
        )
    ) == 1


def test_shared_workspace_returns_messages_for_agent() -> None:
    value = shared_workspace()

    messages = value.messages_for_agent(
        "agent-search-001"
    )

    assert len(messages) == 1
    assert messages[0].message_id == "message-001"


@pytest.mark.parametrize(
    ("method_name", "argument"),
    [
        ("agent", " "),
        ("assignment", " "),
        ("results_for_assignment", " "),
    ],
)
def test_shared_workspace_rejects_blank_lookup(
    method_name: str,
    argument: str,
) -> None:
    value = shared_workspace()
    method = getattr(value, method_name)

    with pytest.raises(ValueError):
        method(argument)


def test_shared_workspace_is_frozen() -> None:
    value = shared_workspace()

    with pytest.raises(ValidationError):
        value.revision_count = 1
