"""Schemas for deterministic failure recovery evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.guardrails.failure_recovery_policy import (
    RecoveryStrategy,
    RecoveryTargetType,
)
from app.guardrails.retry_policy import RetryFailureCategory


class RecoveryDecisionStatus(StrEnum):
    """Final recovery decision status."""

    RECOVER = "recover"
    REVIEW = "review"
    ABORT = "abort"


class RecoveryCandidate(BaseModel):
    """One available fallback resource."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    candidate_id: str
    target_type: RecoveryTargetType
    available: bool = True
    priority: int = Field(default=100, ge=0)
    quality_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    age_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        """Validate candidate-specific fields."""

        if not self.candidate_id.strip():
            raise ValueError(
                "candidate_id must not be blank"
            )

        if (
            self.target_type
            is RecoveryTargetType.PARTIAL_OUTPUT
            and self.quality_score is None
        ):
            raise ValueError(
                "partial output candidate requires "
                "quality_score"
            )

        if (
            self.target_type is RecoveryTargetType.CACHE
            and self.age_seconds is None
        ):
            raise ValueError(
                "cache candidate requires age_seconds"
            )

        return self


class FailureRecoveryContext(BaseModel):
    """Runtime context supplied to recovery evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    failure_id: str
    failure_category: RetryFailureCategory
    error_code: str
    current_tool_name: str | None = None
    current_agent_id: str | None = None
    retry_exhausted: bool
    candidates: list[RecoveryCandidate] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        """Validate context identity and candidate uniqueness."""

        if not self.failure_id.strip():
            raise ValueError(
                "failure_id must not be blank"
            )

        if not self.error_code.strip():
            raise ValueError(
                "error_code must not be blank"
            )

        for field_name, value in {
            "current_tool_name": self.current_tool_name,
            "current_agent_id": self.current_agent_id,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        candidate_ids = [
            candidate.candidate_id.strip().casefold()
            for candidate in self.candidates
        ]

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError(
                "candidates must have unique candidate IDs"
            )

        return self


class FailureRecoveryDecision(BaseModel):
    """Complete failure recovery decision."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    decision_id: str
    policy_id: str
    failure_id: str
    status: RecoveryDecisionStatus
    strategy: RecoveryStrategy
    target_type: RecoveryTargetType
    selected_candidate_id: str | None = None
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Validate decision and target consistency."""

        required_text = {
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "failure_id": self.failure_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        candidate_strategies = {
            RecoveryStrategy.ALTERNATE_TOOL,
            RecoveryStrategy.ALTERNATE_AGENT,
            RecoveryStrategy.CACHED_RESULT,
            RecoveryStrategy.PARTIAL_RESULT,
        }

        if (
            self.strategy in candidate_strategies
            and self.selected_candidate_id is None
        ):
            raise ValueError(
                "candidate recovery strategy requires "
                "selected_candidate_id"
            )

        if (
            self.strategy
            in {
                RecoveryStrategy.MANUAL_REVIEW,
                RecoveryStrategy.ABORT,
            }
            and self.selected_candidate_id is not None
        ):
            raise ValueError(
                "manual review and abort must not select "
                "a candidate"
            )

        if (
            self.status is RecoveryDecisionStatus.REVIEW
            and self.strategy
            is not RecoveryStrategy.MANUAL_REVIEW
        ):
            raise ValueError(
                "review status requires manual_review strategy"
            )

        if (
            self.status is RecoveryDecisionStatus.ABORT
            and self.strategy is not RecoveryStrategy.ABORT
        ):
            raise ValueError(
                "abort status requires abort strategy"
            )

        return self
