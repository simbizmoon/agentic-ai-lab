"""Tests for research-agent capability and permission schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
    ResearchToolPermission,
    ResearchWorkspacePermission,
)


def agent(
    *,
    role: ResearchAgentRole = (
        ResearchAgentRole.MANAGER
    ),
) -> ResearchAgentIdentity:
    """Return one valid research-agent identity."""

    return ResearchAgentIdentity(
        agent_id="agent-manager-001",
        name="Research Manager",
        role=role,
        description=(
            "Coordinates the multi-agent research workflow."
        ),
    )


def tool_permission(
    *,
    tool_name: str = "source_search",
    **overrides: object,
) -> ResearchToolPermission:
    """Return one valid tool permission."""

    values: dict[str, object] = {
        "tool_name": tool_name,
        "description": "Searches research sources.",
        "allowed_operations": [
            "search",
            "inspect",
        ],
        "metadata": {
            "provider": "in-memory",
        },
    }
    values.update(overrides)

    return ResearchToolPermission.model_validate(
        values
    )


def profile(
    **overrides: object,
) -> ResearchAgentCapabilityProfile:
    """Return one valid capability profile."""

    values: dict[str, object] = {
        "profile_id": "profile-manager-001",
        "agent": agent(),
        "capabilities": [
            ResearchAgentCapability.MANAGE_RESEARCH,
            ResearchAgentCapability.DECOMPOSE_TASKS,
            ResearchAgentCapability.APPROVE_RESULT,
        ],
        "workspace_permissions": [
            ResearchWorkspacePermission.READ_REQUEST,
            ResearchWorkspacePermission.READ_TASKS,
            ResearchWorkspacePermission.WRITE_TASKS,
            ResearchWorkspacePermission.READ_QUALITY,
        ],
        "allowed_tools": [
            tool_permission(),
        ],
        "denied_tools": [
            "system_shell",
        ],
        "can_delegate": True,
        "delegatable_roles": [
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentRole.QUALITY_REVIEWER,
        ],
        "metadata": {
            "team": "research",
        },
    }
    values.update(overrides)

    return ResearchAgentCapabilityProfile.model_validate(
        values
    )


def test_tool_permission_accepts_valid_values() -> None:
    value = tool_permission()

    assert value.tool_name == "source_search"
    assert value.allowed_operations == [
        "search",
        "inspect",
    ]


def test_tool_permission_rejects_blank_name() -> None:
    with pytest.raises(
        ValidationError,
        match="tool_name must not be blank",
    ):
        tool_permission(tool_name=" ")


def test_tool_permission_rejects_duplicate_operations() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "allowed_operations must not contain duplicates"
        ),
    ):
        tool_permission(
            allowed_operations=[
                "search",
                " SEARCH ",
            ]
        )


def test_profile_accepts_valid_values() -> None:
    value = profile()

    assert value.can_delegate is True
    assert value.has_capability(
        ResearchAgentCapability.MANAGE_RESEARCH
    )


def test_profile_rejects_blank_profile_id() -> None:
    with pytest.raises(
        ValidationError,
        match="profile_id must not be blank",
    ):
        profile(profile_id=" ")


def test_profile_rejects_duplicate_capabilities() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "capabilities must not contain duplicates"
        ),
    ):
        profile(
            capabilities=[
                ResearchAgentCapability.MANAGE_RESEARCH,
                ResearchAgentCapability.MANAGE_RESEARCH,
            ]
        )


def test_profile_rejects_duplicate_workspace_permissions() -> None:
    permission = (
        ResearchWorkspacePermission.READ_REQUEST
    )

    with pytest.raises(
        ValidationError,
        match=(
            "workspace_permissions must not contain duplicates"
        ),
    ):
        profile(
            workspace_permissions=[
                permission,
                permission,
            ]
        )


def test_profile_rejects_duplicate_allowed_tool_names() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "allowed tool names must not contain duplicates"
        ),
    ):
        profile(
            allowed_tools=[
                tool_permission(
                    tool_name="source_search"
                ),
                tool_permission(
                    tool_name=" SOURCE_SEARCH "
                ),
            ]
        )


def test_profile_rejects_allowed_denied_overlap() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "allowed_tools and denied_tools must not overlap"
        ),
    ):
        profile(
            denied_tools=[" SOURCE_SEARCH "]
        )


def test_profile_rejects_delegation_roles_when_disabled() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "delegatable_roles require can_delegate"
        ),
    ):
        profile(can_delegate=False)


def test_profile_requires_roles_when_delegating() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "delegating profile must define delegatable_roles"
        ),
    ):
        profile(
            can_delegate=True,
            delegatable_roles=[],
        )


def test_profile_rejects_own_delegation_role() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "agent must not delegate to its own role"
        ),
    ):
        profile(
            delegatable_roles=[
                ResearchAgentRole.MANAGER
            ]
        )


def test_profile_checks_workspace_permission() -> None:
    value = profile()

    assert value.can_access_workspace(
        ResearchWorkspacePermission.READ_REQUEST
    )
    assert not value.can_access_workspace(
        ResearchWorkspacePermission.WRITE_REPORT
    )


def test_profile_checks_tool_permission() -> None:
    value = profile()

    assert value.can_use_tool(
        " SOURCE_SEARCH "
    )
    assert not value.can_use_tool(
        "system_shell"
    )
    assert not value.can_use_tool(
        "unknown_tool"
    )


def test_profile_returns_tool_permission() -> None:
    value = profile()

    result = value.tool_permission(
        " SOURCE_SEARCH "
    )

    assert result is not None
    assert result.tool_name == "source_search"
    assert value.tool_permission("missing") is None


def test_profile_rejects_blank_tool_lookup() -> None:
    value = profile()

    with pytest.raises(
        ValueError,
        match="tool_name must not be blank",
    ):
        value.can_use_tool(" ")

    with pytest.raises(
        ValueError,
        match="tool_name must not be blank",
    ):
        value.tool_permission(" ")


def test_profile_checks_delegation_role() -> None:
    value = profile()

    assert value.can_delegate_to(
        ResearchAgentRole.SEARCH_SPECIALIST
    )
    assert not value.can_delegate_to(
        ResearchAgentRole.MANAGER
    )


def test_non_delegating_profile_is_valid() -> None:
    value = profile(
        agent=agent(
            role=ResearchAgentRole.SOURCE_READER
        ),
        can_delegate=False,
        delegatable_roles=[],
    )

    assert value.can_delegate is False
