"""Schemas for research-agent capabilities and permissions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)


class ResearchAgentCapability(StrEnum):
    """Supported high-level research-agent capabilities."""

    MANAGE_RESEARCH = "manage_research"
    DECOMPOSE_TASKS = "decompose_tasks"
    PLAN_QUERIES = "plan_queries"
    SEARCH_SOURCES = "search_sources"
    READ_SOURCES = "read_sources"
    EXTRACT_EVIDENCE = "extract_evidence"
    EVALUATE_SOURCES = "evaluate_sources"
    BUILD_CLAIMS = "build_claims"
    VERIFY_CITATIONS = "verify_citations"
    SYNTHESIZE_REPORT = "synthesize_report"
    EVALUATE_REPORT = "evaluate_report"
    REQUEST_REVISION = "request_revision"
    APPROVE_RESULT = "approve_result"


class ResearchWorkspacePermission(StrEnum):
    """Permissions for accessing shared research workspace data."""

    READ_REQUEST = "read_request"
    READ_TASKS = "read_tasks"
    WRITE_TASKS = "write_tasks"
    READ_QUERIES = "read_queries"
    WRITE_QUERIES = "write_queries"
    READ_SOURCES = "read_sources"
    WRITE_SOURCES = "write_sources"
    READ_DOCUMENTS = "read_documents"
    WRITE_DOCUMENTS = "write_documents"
    READ_EVIDENCE = "read_evidence"
    WRITE_EVIDENCE = "write_evidence"
    READ_CLAIMS = "read_claims"
    WRITE_CLAIMS = "write_claims"
    READ_REPORT = "read_report"
    WRITE_REPORT = "write_report"
    READ_QUALITY = "read_quality"
    WRITE_QUALITY = "write_quality"


class ResearchToolPermission(BaseModel):
    """Explicit permission for one tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    tool_name: str
    description: str | None = None
    allowed_operations: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_tool_permission(self) -> Self:
        """Validate tool name, operations, and metadata."""

        if not self.tool_name.strip():
            raise ValueError(
                "tool_name must not be blank"
            )

        if (
            self.description is not None
            and not self.description.strip()
        ):
            raise ValueError(
                "description must not be blank when provided"
            )

        self._validate_unique_strings(
            self.allowed_operations,
            field_name="allowed_operations",
        )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @staticmethod
    def _validate_unique_strings(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate a list of nonblank unique strings."""

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )


class ResearchAgentCapabilityProfile(BaseModel):
    """Capabilities and permissions assigned to one agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    profile_id: str
    agent: ResearchAgentIdentity
    capabilities: list[
        ResearchAgentCapability
    ] = Field(default_factory=list)
    workspace_permissions: list[
        ResearchWorkspacePermission
    ] = Field(default_factory=list)
    allowed_tools: list[
        ResearchToolPermission
    ] = Field(default_factory=list)
    denied_tools: list[str] = Field(
        default_factory=list
    )
    can_delegate: bool = False
    delegatable_roles: list[
        ResearchAgentRole
    ] = Field(default_factory=list)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        """Validate capability and permission consistency."""

        if not self.profile_id.strip():
            raise ValueError(
                "profile_id must not be blank"
            )

        self._validate_unique_enum_values(
            self.capabilities,
            field_name="capabilities",
        )
        self._validate_unique_enum_values(
            self.workspace_permissions,
            field_name="workspace_permissions",
        )
        self._validate_unique_enum_values(
            self.delegatable_roles,
            field_name="delegatable_roles",
        )

        allowed_tool_names = [
            permission.tool_name.strip().casefold()
            for permission in self.allowed_tools
        ]

        if len(set(allowed_tool_names)) != len(
            allowed_tool_names
        ):
            raise ValueError(
                "allowed tool names must not contain duplicates"
            )

        denied_tool_names = self._validate_denied_tools()

        if set(allowed_tool_names) & denied_tool_names:
            raise ValueError(
                "allowed_tools and denied_tools must not overlap"
            )

        if (
            not self.can_delegate
            and self.delegatable_roles
        ):
            raise ValueError(
                "delegatable_roles require can_delegate"
            )

        if (
            self.can_delegate
            and not self.delegatable_roles
        ):
            raise ValueError(
                "delegating profile must define delegatable_roles"
            )

        if self.agent.role in self.delegatable_roles:
            raise ValueError(
                "agent must not delegate to its own role"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @staticmethod
    def _validate_unique_enum_values(
        values: list[StrEnum],
        *,
        field_name: str,
    ) -> None:
        """Validate uniqueness of enum collections."""

        normalized = [
            value.value.casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    def _validate_denied_tools(self) -> set[str]:
        """Validate and normalize denied tool names."""

        if any(
            not tool_name.strip()
            for tool_name in self.denied_tools
        ):
            raise ValueError(
                "denied_tools must not contain blank values"
            )

        normalized = {
            tool_name.strip().casefold()
            for tool_name in self.denied_tools
        }

        if len(normalized) != len(self.denied_tools):
            raise ValueError(
                "denied_tools must not contain duplicates"
            )

        return normalized

    def has_capability(
        self,
        capability: ResearchAgentCapability,
    ) -> bool:
        """Return whether the agent has a capability."""

        return capability in self.capabilities

    def can_access_workspace(
        self,
        permission: ResearchWorkspacePermission,
    ) -> bool:
        """Return whether the agent has a workspace permission."""

        return permission in self.workspace_permissions

    def can_use_tool(
        self,
        tool_name: str,
    ) -> bool:
        """Return whether the agent may use a named tool."""

        if not tool_name.strip():
            raise ValueError(
                "tool_name must not be blank"
            )

        normalized = tool_name.strip().casefold()

        denied = {
            value.strip().casefold()
            for value in self.denied_tools
        }

        if normalized in denied:
            return False

        return any(
            permission.tool_name.strip().casefold()
            == normalized
            for permission in self.allowed_tools
        )

    def can_delegate_to(
        self,
        role: ResearchAgentRole,
    ) -> bool:
        """Return whether the agent may delegate to a role."""

        return (
            self.can_delegate
            and role in self.delegatable_roles
        )

    def tool_permission(
        self,
        tool_name: str,
    ) -> ResearchToolPermission | None:
        """Return one allowed tool permission by name."""

        if not tool_name.strip():
            raise ValueError(
                "tool_name must not be blank"
            )

        normalized = tool_name.strip().casefold()

        return next(
            (
                permission
                for permission in self.allowed_tools
                if permission.tool_name
                .strip()
                .casefold()
                == normalized
            ),
            None,
        )
