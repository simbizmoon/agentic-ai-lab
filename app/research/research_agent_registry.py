"""In-memory registry for research agents and capability profiles."""

from __future__ import annotations

from collections.abc import Iterable

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
    ResearchWorkspacePermission,
)


class ResearchAgentRegistry:
    """Register and query research agents and capability profiles."""

    def __init__(
        self,
        *,
        agents: Iterable[ResearchAgentIdentity] | None = None,
        profiles: Iterable[
            ResearchAgentCapabilityProfile
        ] | None = None,
    ) -> None:
        self._agents: dict[str, ResearchAgentIdentity] = {}
        self._profiles: dict[
            str,
            ResearchAgentCapabilityProfile,
        ] = {}
        self._profile_id_to_agent_id: dict[str, str] = {}

        for agent in agents or []:
            self.register_agent(agent)

        for profile in profiles or []:
            self.register_profile(profile)

    @staticmethod
    def _normalize_identifier(
        value: str,
        *,
        field_name: str,
    ) -> str:
        """Normalize a required identifier."""

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be blank"
            )

        return value.strip().casefold()

    def register_agent(
        self,
        agent: ResearchAgentIdentity,
    ) -> None:
        """Register one unique research agent."""

        agent_key = self._normalize_identifier(
            agent.agent_id,
            field_name="agent_id",
        )

        if agent_key in self._agents:
            raise ResearchAgentRegistryError(
                "agent ID is already registered"
            )

        self._agents[agent_key] = agent

    def register_profile(
        self,
        profile: ResearchAgentCapabilityProfile,
    ) -> None:
        """Register one capability profile for a registered agent."""

        profile_key = self._normalize_identifier(
            profile.profile_id,
            field_name="profile_id",
        )
        agent_key = self._normalize_identifier(
            profile.agent.agent_id,
            field_name="agent_id",
        )

        if profile_key in self._profile_id_to_agent_id:
            raise ResearchAgentRegistryError(
                "profile ID is already registered"
            )

        registered_agent = self._agents.get(agent_key)

        if registered_agent is None:
            raise ResearchAgentRegistryError(
                "profile agent must be registered first"
            )

        if profile.agent != registered_agent:
            raise ResearchAgentRegistryError(
                "profile agent must match registered agent"
            )

        if agent_key in self._profiles:
            raise ResearchAgentRegistryError(
                "agent already has a registered profile"
            )

        self._profiles[agent_key] = profile
        self._profile_id_to_agent_id[profile_key] = agent_key

    def unregister_agent(
        self,
        agent_id: str,
    ) -> ResearchAgentIdentity:
        """Remove one agent and its capability profile."""

        agent_key = self._normalize_identifier(
            agent_id,
            field_name="agent_id",
        )

        agent = self._agents.pop(agent_key, None)

        if agent is None:
            raise ResearchAgentRegistryError(
                "agent is not registered"
            )

        profile = self._profiles.pop(agent_key, None)

        if profile is not None:
            profile_key = self._normalize_identifier(
                profile.profile_id,
                field_name="profile_id",
            )
            self._profile_id_to_agent_id.pop(
                profile_key,
                None,
            )

        return agent

    def unregister_profile(
        self,
        profile_id: str,
    ) -> ResearchAgentCapabilityProfile:
        """Remove one capability profile without removing its agent."""

        profile_key = self._normalize_identifier(
            profile_id,
            field_name="profile_id",
        )

        agent_key = self._profile_id_to_agent_id.pop(
            profile_key,
            None,
        )

        if agent_key is None:
            raise ResearchAgentRegistryError(
                "profile is not registered"
            )

        profile = self._profiles.pop(agent_key)

        return profile

    def agent(
        self,
        agent_id: str,
    ) -> ResearchAgentIdentity | None:
        """Return one registered agent by normalized ID."""

        agent_key = self._normalize_identifier(
            agent_id,
            field_name="agent_id",
        )

        return self._agents.get(agent_key)

    def require_agent(
        self,
        agent_id: str,
    ) -> ResearchAgentIdentity:
        """Return one registered agent or raise an error."""

        agent = self.agent(agent_id)

        if agent is None:
            raise ResearchAgentRegistryError(
                "agent is not registered"
            )

        return agent

    def profile_for_agent(
        self,
        agent_id: str,
    ) -> ResearchAgentCapabilityProfile | None:
        """Return the capability profile for one agent."""

        agent_key = self._normalize_identifier(
            agent_id,
            field_name="agent_id",
        )

        return self._profiles.get(agent_key)

    def require_profile_for_agent(
        self,
        agent_id: str,
    ) -> ResearchAgentCapabilityProfile:
        """Return one agent profile or raise an error."""

        profile = self.profile_for_agent(agent_id)

        if profile is None:
            raise ResearchAgentRegistryError(
                "agent does not have a registered profile"
            )

        return profile

    def profile(
        self,
        profile_id: str,
    ) -> ResearchAgentCapabilityProfile | None:
        """Return one capability profile by profile ID."""

        profile_key = self._normalize_identifier(
            profile_id,
            field_name="profile_id",
        )

        agent_key = self._profile_id_to_agent_id.get(
            profile_key
        )

        if agent_key is None:
            return None

        return self._profiles[agent_key]

    def agents(
        self,
    ) -> list[ResearchAgentIdentity]:
        """Return all agents in registration order."""

        return list(self._agents.values())

    def profiles(
        self,
    ) -> list[ResearchAgentCapabilityProfile]:
        """Return all profiles in agent registration order."""

        return [
            self._profiles[agent_key]
            for agent_key in self._agents
            if agent_key in self._profiles
        ]

    def agents_by_role(
        self,
        role: ResearchAgentRole,
        *,
        available_only: bool = False,
    ) -> list[ResearchAgentIdentity]:
        """Return registered agents with one role."""

        return [
            agent
            for agent in self._agents.values()
            if agent.role is role
            and (
                not available_only
                or agent.status
                is ResearchAgentStatus.AVAILABLE
            )
        ]

    def available_agents(
        self,
    ) -> list[ResearchAgentIdentity]:
        """Return all agents currently available for work."""

        return [
            agent
            for agent in self._agents.values()
            if agent.status
            is ResearchAgentStatus.AVAILABLE
        ]

    def agents_with_capability(
        self,
        capability: ResearchAgentCapability,
        *,
        available_only: bool = True,
    ) -> list[ResearchAgentIdentity]:
        """Return agents whose profile grants a capability."""

        matches: list[ResearchAgentIdentity] = []

        for agent_key, agent in self._agents.items():
            profile = self._profiles.get(agent_key)

            if profile is None:
                continue

            if not profile.has_capability(capability):
                continue

            if (
                available_only
                and agent.status
                is not ResearchAgentStatus.AVAILABLE
            ):
                continue

            matches.append(agent)

        return matches

    def agents_with_workspace_permission(
        self,
        permission: ResearchWorkspacePermission,
        *,
        available_only: bool = True,
    ) -> list[ResearchAgentIdentity]:
        """Return agents granted one workspace permission."""

        matches: list[ResearchAgentIdentity] = []

        for agent_key, agent in self._agents.items():
            profile = self._profiles.get(agent_key)

            if profile is None:
                continue

            if not profile.can_access_workspace(
                permission
            ):
                continue

            if (
                available_only
                and agent.status
                is not ResearchAgentStatus.AVAILABLE
            ):
                continue

            matches.append(agent)

        return matches

    def agents_allowed_to_use_tool(
        self,
        tool_name: str,
        *,
        available_only: bool = True,
    ) -> list[ResearchAgentIdentity]:
        """Return agents whose profiles allow one tool."""

        normalized_tool_name = self._normalize_identifier(
            tool_name,
            field_name="tool_name",
        )

        matches: list[ResearchAgentIdentity] = []

        for agent_key, agent in self._agents.items():
            profile = self._profiles.get(agent_key)

            if profile is None:
                continue

            if not profile.can_use_tool(
                normalized_tool_name
            ):
                continue

            if (
                available_only
                and agent.status
                is not ResearchAgentStatus.AVAILABLE
            ):
                continue

            matches.append(agent)

        return matches

    def delegation_targets(
        self,
        assigner_agent_id: str,
        role: ResearchAgentRole,
        *,
        available_only: bool = True,
    ) -> list[ResearchAgentIdentity]:
        """Return agents an assigner may delegate to for one role."""

        assigner_profile = self.require_profile_for_agent(
            assigner_agent_id
        )

        if not assigner_profile.can_delegate_to(role):
            return []

        return [
            agent
            for agent in self.agents_by_role(
                role,
                available_only=available_only,
            )
            if (
                agent.agent_id.strip().casefold()
                != assigner_profile.agent.agent_id
                .strip()
                .casefold()
            )
        ]

    def contains_agent(
        self,
        agent_id: str,
    ) -> bool:
        """Return whether an agent ID is registered."""

        return self.agent(agent_id) is not None

    def contains_profile(
        self,
        profile_id: str,
    ) -> bool:
        """Return whether a profile ID is registered."""

        return self.profile(profile_id) is not None

    def __len__(self) -> int:
        """Return the number of registered agents."""

        return len(self._agents)
