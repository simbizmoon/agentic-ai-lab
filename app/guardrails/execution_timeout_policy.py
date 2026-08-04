"""Schemas for deterministic execution timeout policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ExecutionSubjectType(StrEnum):
    """Type of execution controlled by a timeout policy."""

    AGENT = "agent"
    TOOL = "tool"
    ASSIGNMENT = "assignment"
    WORKFLOW = "workflow"
    EVALUATION = "evaluation"


class TimeoutPolicy(BaseModel):
    """Versioned timeout and cancellation policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    policy_id: str
    name: str
    description: str
    version: str
    subject_type: ExecutionSubjectType
    soft_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
    )
    hard_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
    )
    cancellation_grace_period_seconds: float = Field(
        default=5.0,
        ge=0,
    )
    warn_on_soft_timeout: bool = True
    cancel_on_hard_timeout: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        """Validate timeout policy consistency."""

        required_text = {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.soft_timeout_seconds is None
            and self.hard_timeout_seconds is None
        ):
            raise ValueError(
                "timeout policy requires a soft or hard timeout"
            )

        if (
            self.soft_timeout_seconds is not None
            and self.hard_timeout_seconds is not None
            and self.soft_timeout_seconds
            >= self.hard_timeout_seconds
        ):
            raise ValueError(
                "soft_timeout_seconds must be less than "
                "hard_timeout_seconds"
            )

        if (
            self.warn_on_soft_timeout
            and self.soft_timeout_seconds is None
        ):
            raise ValueError(
                "warn_on_soft_timeout requires "
                "soft_timeout_seconds"
            )

        if (
            self.cancel_on_hard_timeout
            and self.hard_timeout_seconds is None
        ):
            raise ValueError(
                "cancel_on_hard_timeout requires "
                "hard_timeout_seconds"
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


def default_agent_timeout_policy() -> TimeoutPolicy:
    """Return the default AIRA agent timeout policy."""

    return TimeoutPolicy(
        policy_id="aira-agent-timeout-v1",
        name="AIRA Agent Timeout Policy",
        description=(
            "Warn on prolonged agent execution and terminate "
            "agents that exceed the hard runtime limit."
        ),
        version="1.0.0",
        subject_type=ExecutionSubjectType.AGENT,
        soft_timeout_seconds=120.0,
        hard_timeout_seconds=300.0,
        cancellation_grace_period_seconds=10.0,
        warn_on_soft_timeout=True,
        cancel_on_hard_timeout=True,
    )
