"""Schemas for deterministic agent tool permissions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.schemas.research_agent import ResearchAgentRole


class ToolAccessMode(StrEnum):
    """Access mode allowed for one tool."""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class ToolRiskLevel(StrEnum):
    """Risk level associated with one tool operation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolPermissionRule(BaseModel):
    """Permission rule for one tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    tool_name: str
    allowed_operations: list[str] = Field(min_length=1)
    access_mode: ToolAccessMode = ToolAccessMode.READ_ONLY
    allow_external_network: bool = False
    allow_sensitive_operations: bool = False
    maximum_calls: int | None = Field(default=None, ge=1)
    allowed_roles: list[ResearchAgentRole] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        """Validate tool rule identity and uniqueness."""

        if not self.tool_name.strip():
            raise ValueError(
                "tool_name must not be blank"
            )

        self._validate_unique_text(
            self.allowed_operations,
            field_name="allowed_operations",
        )

        if len(set(self.allowed_roles)) != len(
            self.allowed_roles
        ):
            raise ValueError(
                "allowed_roles must not contain duplicates"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique strings."""

        if any(not value.strip() for value in values):
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

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata values."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class AgentToolPermissionProfile(BaseModel):
    """Tool permission profile assigned to one agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    profile_id: str
    agent_id: str
    agent_role: ResearchAgentRole
    rules: list[ToolPermissionRule] = Field(
        default_factory=list
    )
    default_deny: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        """Validate permission profile and unique tools."""

        if not self.profile_id.strip():
            raise ValueError(
                "profile_id must not be blank"
            )

        if not self.agent_id.strip():
            raise ValueError(
                "agent_id must not be blank"
            )

        tool_names = [
            rule.tool_name.strip().casefold()
            for rule in self.rules
        ]

        if len(set(tool_names)) != len(tool_names):
            raise ValueError(
                "rules must have unique tool names"
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

    def rule_for_tool(
        self,
        tool_name: str,
    ) -> ToolPermissionRule | None:
        """Return one rule using case-insensitive matching."""

        normalized = tool_name.strip().casefold()

        return next(
            (
                rule
                for rule in self.rules
                if rule.tool_name.strip().casefold()
                == normalized
            ),
            None,
        )


class ToolCallRequest(BaseModel):
    """One requested tool operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    call_id: str
    request_id: str
    workspace_id: str
    agent_id: str
    agent_role: ResearchAgentRole
    tool_name: str
    operation: str
    write_operation: bool = False
    external_network: bool = False
    sensitive_operation: bool = False
    sensitive_operation_approved: bool = False
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    arguments: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate tool-call request identity and semantics."""

        required_text = {
            "call_id": self.call_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "operation": self.operation,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.sensitive_operation_approved
            and not self.sensitive_operation
        ):
            raise ValueError(
                "sensitive approval requires "
                "sensitive_operation"
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
