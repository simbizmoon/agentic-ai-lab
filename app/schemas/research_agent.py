"""Schemas for research-agent identity and roles."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResearchAgentRole(StrEnum):
    """Supported specialist roles in the research system."""

    MANAGER = "manager"
    SEARCH_SPECIALIST = "search_specialist"
    SOURCE_READER = "source_reader"
    EVIDENCE_ANALYST = "evidence_analyst"
    SOURCE_CRITIC = "source_critic"
    CLAIM_ANALYST = "claim_analyst"
    CITATION_VERIFIER = "citation_verifier"
    SYNTHESIS_SPECIALIST = "synthesis_specialist"
    QUALITY_REVIEWER = "quality_reviewer"


class ResearchAgentStatus(StrEnum):
    """Current availability state of one research agent."""

    AVAILABLE = "available"
    BUSY = "busy"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class ResearchAgentIdentity(BaseModel):
    """Stable identity and role of one research agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    agent_id: str
    name: str
    role: ResearchAgentRole
    description: str
    status: ResearchAgentStatus = (
        ResearchAgentStatus.AVAILABLE
    )
    version: str = "1.0"
    tags: list[str] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        """Validate identity fields and normalized collections."""

        required_text = {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        normalized_tags = [
            tag.strip().casefold()
            for tag in self.tags
        ]

        if any(
            not tag.strip()
            for tag in self.tags
        ):
            raise ValueError(
                "tags must not contain blank values"
            )

        if len(set(normalized_tags)) != len(
            normalized_tags
        ):
            raise ValueError(
                "tags must not contain duplicates"
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

    @property
    def is_available(self) -> bool:
        """Return whether the agent can accept new work."""

        return (
            self.status
            is ResearchAgentStatus.AVAILABLE
        )

    def has_role(
        self,
        role: ResearchAgentRole,
    ) -> bool:
        """Return whether the agent has the given role."""

        return self.role is role
