"""Tests for the in-memory research-agent registry."""

import pytest

from app.research.research_agent_registry import (
    ResearchAgentRegistry,
)
from app.research.research_agent_registry_error import (
    ResearchAgentRegistryError,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
    ResearchAgentStatus,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
    ResearchToolPermission,
    ResearchWorkspacePermission,
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
    """Return one search specialist identity."""

    return identity(
        agent_id=agent_id,
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name=f"Search Specialist {agent_id}",
        status=status,
    )


def reader_agent() -> ResearchAgentIdentity:
    """Return one source reader identity."""

    return identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )


def manager_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return one manager capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=agent or manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
            ResearchAgentCapability.DECOMPOSE_TASKS,
        ],
        workspace_permissions=[
            ResearchWorkspacePermission.READ_REQUEST,
            ResearchWorkspacePermission.WRITE_TASKS,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentRole.SOURCE_READER,
        ],
    )


def search_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    profile_id: str = "profile-search-001",
) -> ResearchAgentCapabilityProfile:
    """Return one search specialist capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id=profile_id,
        agent=agent or search_agent(),
        capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        workspace_permissions=[
            ResearchWorkspacePermission.READ_QUERIES,
            ResearchWorkspacePermission.WRITE_SOURCES,
        ],
        allowed_tools=[
            ResearchToolPermission(
                tool_name="source_search",
                allowed_operations=["search"],
            )
        ],
    )


def reader_profile() -> ResearchAgentCapabilityProfile:
    """Return one source reader capability profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-reader-001",
        agent=reader_agent(),
        capabilities=[
            ResearchAgentCapability.READ_SOURCES,
        ],
        workspace_permissions=[
            ResearchWorkspacePermission.READ_SOURCES,
            ResearchWorkspacePermission.WRITE_DOCUMENTS,
        ],
        allowed_tools=[
            ResearchToolPermission(
                tool_name="source_reader",
                allowed_operations=["read"],
            )
        ],
    )


def populated_registry() -> ResearchAgentRegistry:
    """Return one registry with manager, searcher, and reader."""

    return ResearchAgentRegistry(
        agents=[
            manager(),
            search_agent(),
            reader_agent(),
        ],
        profiles=[
            manager_profile(),
            search_profile(),
            reader_profile(),
        ],
    )


def test_registry_registers_agent_and_profile() -> None:
    registry = ResearchAgentRegistry()
    agent = search_agent()
    profile = search_profile(agent=agent)

    registry.register_agent(agent)
    registry.register_profile(profile)

    assert len(registry) == 1
    assert registry.agent(" AGENT-SEARCH-001 ") == agent
    assert (
        registry.profile_for_agent(
            "agent-search-001"
        )
        == profile
    )


def test_registry_rejects_duplicate_agent_id() -> None:
    registry = ResearchAgentRegistry()
    registry.register_agent(search_agent())

    with pytest.raises(
        ResearchAgentRegistryError,
        match="agent ID is already registered",
    ):
        registry.register_agent(
            search_agent(
                agent_id=" AGENT-SEARCH-001 "
            )
        )


def test_registry_requires_agent_before_profile() -> None:
    registry = ResearchAgentRegistry()

    with pytest.raises(
        ResearchAgentRegistryError,
        match=(
            "profile agent must be registered first"
        ),
    ):
        registry.register_profile(search_profile())


def test_registry_rejects_mismatched_profile_agent() -> None:
    registry = ResearchAgentRegistry()
    registered = search_agent()
    registry.register_agent(registered)

    changed_identity = ResearchAgentIdentity(
        agent_id=registered.agent_id,
        name="Different Search Agent",
        role=registered.role,
        description="Different identity.",
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match=(
            "profile agent must match registered agent"
        ),
    ):
        registry.register_profile(
            search_profile(agent=changed_identity)
        )


def test_registry_rejects_second_profile_for_agent() -> None:
    registry = ResearchAgentRegistry()
    agent = search_agent()

    registry.register_agent(agent)
    registry.register_profile(
        search_profile(agent=agent)
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match=(
            "agent already has a registered profile"
        ),
    ):
        registry.register_profile(
            search_profile(
                agent=agent,
                profile_id="profile-search-002",
            )
        )


def test_registry_rejects_duplicate_profile_id() -> None:
    first = search_agent()
    second = search_agent(
        agent_id="agent-search-002"
    )
    registry = ResearchAgentRegistry(
        agents=[first, second]
    )

    registry.register_profile(
        search_profile(agent=first)
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match="profile ID is already registered",
    ):
        registry.register_profile(
            search_profile(
                agent=second,
                profile_id=" PROFILE-SEARCH-001 ",
            )
        )


def test_registry_returns_agents_in_registration_order() -> None:
    registry = populated_registry()

    assert [
        agent.agent_id
        for agent in registry.agents()
    ] == [
        "agent-manager-001",
        "agent-search-001",
        "agent-reader-001",
    ]


def test_registry_returns_profiles_in_agent_order() -> None:
    registry = populated_registry()

    assert [
        profile.profile_id
        for profile in registry.profiles()
    ] == [
        "profile-manager-001",
        "profile-search-001",
        "profile-reader-001",
    ]


def test_registry_filters_agents_by_role() -> None:
    busy_searcher = search_agent(
        agent_id="agent-search-002",
        status=ResearchAgentStatus.BUSY,
    )

    registry = ResearchAgentRegistry(
        agents=[
            search_agent(),
            busy_searcher,
        ]
    )

    assert len(
        registry.agents_by_role(
            ResearchAgentRole.SEARCH_SPECIALIST
        )
    ) == 2

    assert [
        agent.agent_id
        for agent in registry.agents_by_role(
            ResearchAgentRole.SEARCH_SPECIALIST,
            available_only=True,
        )
    ] == [
        "agent-search-001"
    ]


def test_registry_returns_available_agents() -> None:
    registry = ResearchAgentRegistry(
        agents=[
            search_agent(),
            search_agent(
                agent_id="agent-search-002",
                status=ResearchAgentStatus.BUSY,
            ),
        ]
    )

    assert [
        agent.agent_id
        for agent in registry.available_agents()
    ] == [
        "agent-search-001"
    ]


def test_registry_filters_by_capability() -> None:
    registry = populated_registry()

    assert [
        agent.agent_id
        for agent in registry.agents_with_capability(
            ResearchAgentCapability.SEARCH_SOURCES
        )
    ] == [
        "agent-search-001"
    ]


def test_registry_filters_by_workspace_permission() -> None:
    registry = populated_registry()

    assert [
        agent.agent_id
        for agent
        in registry.agents_with_workspace_permission(
            ResearchWorkspacePermission.WRITE_DOCUMENTS
        )
    ] == [
        "agent-reader-001"
    ]


def test_registry_filters_by_tool_permission() -> None:
    registry = populated_registry()

    assert [
        agent.agent_id
        for agent
        in registry.agents_allowed_to_use_tool(
            " SOURCE_SEARCH "
        )
    ] == [
        "agent-search-001"
    ]


def test_registry_returns_delegation_targets() -> None:
    registry = populated_registry()

    targets = registry.delegation_targets(
        "agent-manager-001",
        ResearchAgentRole.SEARCH_SPECIALIST,
    )

    assert [
        agent.agent_id
        for agent in targets
    ] == [
        "agent-search-001"
    ]


def test_registry_returns_no_unauthorized_targets() -> None:
    registry = populated_registry()

    assert registry.delegation_targets(
        "agent-search-001",
        ResearchAgentRole.SOURCE_READER,
    ) == []


def test_registry_requires_profile_for_delegation() -> None:
    registry = ResearchAgentRegistry(
        agents=[manager()]
    )

    with pytest.raises(
        ResearchAgentRegistryError,
        match=(
            "agent does not have a registered profile"
        ),
    ):
        registry.delegation_targets(
            "agent-manager-001",
            ResearchAgentRole.SEARCH_SPECIALIST,
        )


def test_registry_unregisters_profile() -> None:
    registry = populated_registry()

    removed = registry.unregister_profile(
        " PROFILE-SEARCH-001 "
    )

    assert removed.profile_id == "profile-search-001"
    assert (
        registry.profile_for_agent(
            "agent-search-001"
        )
        is None
    )
    assert registry.contains_agent(
        "agent-search-001"
    )


def test_registry_unregisters_agent_and_profile() -> None:
    registry = populated_registry()

    removed = registry.unregister_agent(
        " AGENT-SEARCH-001 "
    )

    assert removed.agent_id == "agent-search-001"
    assert not registry.contains_agent(
        "agent-search-001"
    )
    assert not registry.contains_profile(
        "profile-search-001"
    )


def test_registry_rejects_missing_unregister() -> None:
    registry = ResearchAgentRegistry()

    with pytest.raises(
        ResearchAgentRegistryError,
        match="agent is not registered",
    ):
        registry.unregister_agent("missing-agent")

    with pytest.raises(
        ResearchAgentRegistryError,
        match="profile is not registered",
    ):
        registry.unregister_profile("missing-profile")


def test_registry_requires_registered_agent() -> None:
    registry = ResearchAgentRegistry()

    with pytest.raises(
        ResearchAgentRegistryError,
        match="agent is not registered",
    ):
        registry.require_agent("missing-agent")


@pytest.mark.parametrize(
    ("method_name", "value"),
    [
        ("agent", " "),
        ("profile", " "),
        ("profile_for_agent", " "),
        ("contains_agent", " "),
        ("contains_profile", " "),
        ("unregister_agent", " "),
        ("unregister_profile", " "),
    ],
)
def test_registry_rejects_blank_identifiers(
    method_name: str,
    value: str,
) -> None:
    registry = ResearchAgentRegistry()
    method = getattr(registry, method_name)

    with pytest.raises(ValueError):
        method(value)


def test_registry_rejects_blank_tool_name() -> None:
    with pytest.raises(
        ValueError,
        match="tool_name must not be blank",
    ):
        populated_registry().agents_allowed_to_use_tool(
            " "
        )


def test_registry_returns_defensive_lists() -> None:
    registry = populated_registry()

    agents = registry.agents()
    profiles = registry.profiles()

    agents.clear()
    profiles.clear()

    assert len(registry) == 3
    assert len(registry.profiles()) == 3
