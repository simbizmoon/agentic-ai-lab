"""Tests for the deterministic research manager agent."""

from datetime import UTC, datetime

import pytest

from app.research.in_memory_research_agent_message_bus import (
    InMemoryResearchAgentMessageBus,
)
from app.research.research_agent_registry import (
    ResearchAgentRegistry,
)
from app.research.research_manager_agent import (
    ResearchManagerAgent,
)
from app.research.research_manager_agent_error import (
    ResearchManagerAgentError,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
    ResearchAgentStatus,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentPriority,
    ResearchAgentAssignmentStatus,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_agent_message import (
    ResearchAgentMessagePriority,
    ResearchAgentMessageType,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
    status: ResearchAgentStatus = (
        ResearchAgentStatus.AVAILABLE
    ),
) -> ResearchAgentIdentity:
    """Return one research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
        status=status,
    )


def manager() -> ResearchAgentIdentity:
    """Return one manager identity."""

    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def search_agent(
    *,
    agent_id: str = "agent-search-001",
    status: ResearchAgentStatus = (
        ResearchAgentStatus.AVAILABLE
    ),
) -> ResearchAgentIdentity:
    """Return one search specialist."""

    return identity(
        agent_id=agent_id,
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name=f"Search Specialist {agent_id}",
        status=status,
    )


def manager_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    delegatable_roles: list[
        ResearchAgentRole
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return one manager capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=agent or manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=(
            delegatable_roles
            if delegatable_roles is not None
            else [
                ResearchAgentRole.SEARCH_SPECIALIST,
                ResearchAgentRole.SOURCE_READER,
            ]
        ),
    )


def search_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
    profile_id: str = "profile-search-001",
) -> ResearchAgentCapabilityProfile:
    """Return one search specialist profile."""

    return ResearchAgentCapabilityProfile(
        profile_id=profile_id,
        agent=agent or search_agent(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.SEARCH_SOURCES,
                ResearchAgentCapability.PLAN_QUERIES,
            ]
        ),
    )


def registry(
    *,
    specialist: ResearchAgentIdentity | None = None,
    specialist_profile: (
        ResearchAgentCapabilityProfile | None
    ) = None,
    manager_value: ResearchAgentIdentity | None = None,
    manager_profile_value: (
        ResearchAgentCapabilityProfile | None
    ) = None,
) -> ResearchAgentRegistry:
    """Return one populated research-agent registry."""

    resolved_manager = manager_value or manager()
    resolved_specialist = specialist or search_agent()

    return ResearchAgentRegistry(
        agents=[
            resolved_manager,
            resolved_specialist,
        ],
        profiles=[
            (
                manager_profile_value
                or manager_profile(
                    agent=resolved_manager
                )
            ),
            (
                specialist_profile
                or search_profile(
                    agent=resolved_specialist
                )
            ),
        ],
    )


def create_manager(
    *,
    registry_value: ResearchAgentRegistry | None = None,
) -> tuple[
    ResearchManagerAgent,
    InMemoryResearchAgentMessageBus,
]:
    """Return deterministic manager and message bus."""

    resolved_registry = registry_value or registry()

    message_bus = InMemoryResearchAgentMessageBus(
        registry=resolved_registry,
        now=lambda: datetime(
            2026,
            8,
            4,
            5,
            30,
            tzinfo=UTC,
        ),
        delivery_id_factory=lambda: "delivery-001",
    )

    manager_agent = ResearchManagerAgent(
        manager_agent_id="agent-manager-001",
        registry=resolved_registry,
        message_bus=message_bus,
        now=lambda: datetime(
            2026,
            8,
            4,
            5,
            29,
            tzinfo=UTC,
        ),
        assignment_id_factory=(
            lambda: "assignment-001"
        ),
        message_id_factory=lambda: "message-001",
        correlation_id_factory=(
            lambda: "correlation-001"
        ),
    )

    return manager_agent, message_bus


def dispatch(
    manager_agent: ResearchManagerAgent,
):
    """Dispatch one valid source-search assignment."""

    return manager_agent.dispatch(
        request_id="research-001",
        workspace_id="workspace-001",
        research_task_id="task-001",
        required_role=(
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        required_capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        title="Find authoritative sources",
        objective=(
            "Find sources about multi-agent research."
        ),
        instructions=[
            "Use the approved search queries.",
            "Prefer primary sources.",
        ],
        expected_output_type=(
            "research_source_candidate_set"
        ),
        acceptance_criteria=[
            "Return at least one source.",
        ],
        assignment_priority=(
            ResearchAgentAssignmentPriority.HIGH
        ),
        message_priority=(
            ResearchAgentMessagePriority.HIGH
        ),
        maximum_attempts=2,
        metadata={
            "origin": "research-manager",
        },
    )


def test_manager_dispatches_assignment_and_message() -> None:
    manager_agent, message_bus = create_manager()

    result = dispatch(manager_agent)

    assert result.assignment.assignment_id == (
        "assignment-001"
    )
    assert result.assignment.assignee.agent_id == (
        "agent-search-001"
    )
    assert result.assignment.status is (
        ResearchAgentAssignmentStatus.OFFERED
    )
    assert result.message.message_id == "message-001"
    assert result.message.message_type is (
        ResearchAgentMessageType.TASK_REQUEST
    )
    assert result.message.assignment_id == (
        result.assignment.assignment_id
    )
    assert len(result.deliveries) == 1
    assert message_bus.pending_count(
        "agent-search-001"
    ) == 1


def test_manager_dispatch_preserves_shared_ids() -> None:
    manager_agent, _ = create_manager()

    result = dispatch(manager_agent)

    assert result.assignment.request_id == (
        result.message.request_id
    )
    assert result.assignment.workspace_id == (
        result.message.workspace_id
    )
    assert result.message.correlation_id == (
        "correlation-001"
    )


def test_manager_selects_first_qualified_agent() -> None:
    first = search_agent(
        agent_id="agent-search-001"
    )
    second = search_agent(
        agent_id="agent-search-002"
    )

    registry_value = ResearchAgentRegistry(
        agents=[
            manager(),
            first,
            second,
        ],
        profiles=[
            manager_profile(),
            search_profile(
                agent=first,
                profile_id="profile-search-001",
            ),
            search_profile(
                agent=second,
                profile_id="profile-search-002",
            ),
        ],
    )

    manager_agent, _ = create_manager(
        registry_value=registry_value
    )

    result = dispatch(manager_agent)

    assert result.assignment.assignee.agent_id == (
        "agent-search-001"
    )


def test_manager_skips_unqualified_agent() -> None:
    first = search_agent(
        agent_id="agent-search-001"
    )
    second = search_agent(
        agent_id="agent-search-002"
    )

    registry_value = ResearchAgentRegistry(
        agents=[
            manager(),
            first,
            second,
        ],
        profiles=[
            manager_profile(),
            search_profile(
                agent=first,
                capabilities=[
                    ResearchAgentCapability.PLAN_QUERIES,
                ],
                profile_id="profile-search-001",
            ),
            search_profile(
                agent=second,
                profile_id="profile-search-002",
            ),
        ],
    )

    manager_agent, _ = create_manager(
        registry_value=registry_value
    )

    result = dispatch(manager_agent)

    assert result.assignment.assignee.agent_id == (
        "agent-search-002"
    )


def test_manager_rejects_missing_qualified_agent() -> None:
    specialist = search_agent()
    registry_value = registry(
        specialist=specialist,
        specialist_profile=search_profile(
            agent=specialist,
            capabilities=[
                ResearchAgentCapability.PLAN_QUERIES,
            ],
        ),
    )
    manager_agent, _ = create_manager(
        registry_value=registry_value
    )

    with pytest.raises(
        ResearchManagerAgentError,
        match=(
            "no available qualified agent "
            "for requested role and capabilities"
        ),
    ):
        dispatch(manager_agent)


def test_manager_rejects_busy_specialist() -> None:
    busy = search_agent(
        status=ResearchAgentStatus.BUSY
    )
    registry_value = registry(
        specialist=busy,
        specialist_profile=search_profile(
            agent=busy
        ),
    )
    manager_agent, _ = create_manager(
        registry_value=registry_value
    )

    with pytest.raises(
        ResearchManagerAgentError,
        match=(
            "no available qualified agent "
            "for requested role and capabilities"
        ),
    ):
        dispatch(manager_agent)


def test_manager_rejects_unauthorized_role() -> None:
    manager_agent, _ = create_manager()

    with pytest.raises(
        ResearchManagerAgentError,
        match=(
            "no available qualified agent "
            "for requested role and capabilities"
        ),
    ):
        manager_agent.dispatch(
            request_id="research-001",
            workspace_id="workspace-001",
            required_role=(
                ResearchAgentRole.QUALITY_REVIEWER
            ),
            required_capabilities=[
                ResearchAgentCapability.EVALUATE_REPORT,
            ],
            title="Review report",
            objective="Review report quality.",
            instructions=["Evaluate the report."],
            expected_output_type="quality_review",
            acceptance_criteria=[
                "Return a quality decision."
            ],
        )


def test_manager_constructor_requires_manager_role() -> None:
    wrong_manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Wrong Manager",
    )
    specialist = search_agent()

    registry_value = ResearchAgentRegistry(
        agents=[
            wrong_manager,
            specialist,
        ],
        profiles=[
            ResearchAgentCapabilityProfile(
                profile_id="profile-manager-001",
                agent=wrong_manager,
                capabilities=[
                    ResearchAgentCapability.READ_SOURCES,
                ],
                can_delegate=True,
                delegatable_roles=[
                    ResearchAgentRole.SEARCH_SPECIALIST,
                ],
            ),
            search_profile(agent=specialist),
        ],
    )

    message_bus = InMemoryResearchAgentMessageBus(
        registry=registry_value
    )

    with pytest.raises(
        ResearchManagerAgentError,
        match=(
            "manager agent must have manager role"
        ),
    ):
        ResearchManagerAgent(
            manager_agent_id="agent-manager-001",
            registry=registry_value,
            message_bus=message_bus,
        )


def test_manager_rejects_duplicate_capabilities() -> None:
    manager_agent, _ = create_manager()

    with pytest.raises(
        ValueError,
        match=(
            "required_capabilities must not "
            "contain duplicates"
        ),
    ):
        manager_agent.dispatch(
            request_id="research-001",
            workspace_id="workspace-001",
            required_role=(
                ResearchAgentRole.SEARCH_SPECIALIST
            ),
            required_capabilities=[
                ResearchAgentCapability.SEARCH_SOURCES,
                ResearchAgentCapability.SEARCH_SOURCES,
            ],
            title="Search",
            objective="Search sources.",
            instructions=["Search sources."],
            expected_output_type="source_set",
            acceptance_criteria=[
                "Return one source."
            ],
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "request_id",
        "workspace_id",
        "title",
        "objective",
        "expected_output_type",
    ],
)
def test_manager_rejects_blank_required_text(
    field_name: str,
) -> None:
    manager_agent, _ = create_manager()

    values: dict[str, object] = {
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "required_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "required_capabilities": [
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        "title": "Search",
        "objective": "Search sources.",
        "instructions": ["Search sources."],
        "expected_output_type": "source_set",
        "acceptance_criteria": [
            "Return one source."
        ],
    }
    values[field_name] = " "

    with pytest.raises(
        ValueError,
        match=f"{field_name} must not be blank",
    ):
        manager_agent.dispatch(**values)


def test_manager_rejects_blank_generated_assignment_id() -> None:
    registry_value = registry()
    message_bus = InMemoryResearchAgentMessageBus(
        registry=registry_value
    )
    manager_agent = ResearchManagerAgent(
        manager_agent_id="agent-manager-001",
        registry=registry_value,
        message_bus=message_bus,
        assignment_id_factory=lambda: " ",
    )

    with pytest.raises(
        ResearchManagerAgentError,
        match=(
            "assignment_id factory returned blank value"
        ),
    ):
        dispatch(manager_agent)


def test_manager_exposes_identity() -> None:
    manager_agent, _ = create_manager()

    assert manager_agent.identity.agent_id == (
        "agent-manager-001"
    )
