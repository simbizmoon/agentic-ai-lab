"""Schemas for deterministic failure recovery policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.guardrails.retry_policy import RetryFailureCategory


class RecoveryStrategy(StrEnum):
    """Supported failure recovery strategy."""

    ALTERNATE_TOOL = "alternate_tool"
    ALTERNATE_AGENT = "alternate_agent"
    CACHED_RESULT = "cached_result"
    PARTIAL_RESULT = "partial_result"
    MANUAL_REVIEW = "manual_review"
    ABORT = "abort"


class RecoveryTargetType(StrEnum):
    """Type of target selected by recovery."""

    TOOL = "tool"
    AGENT = "agent"
    CACHE = "cache"
    PARTIAL_OUTPUT = "partial_output"
    HUMAN = "human"
    NONE = "none"


class RecoveryStrategyRule(BaseModel):
    """One ordered recovery strategy rule."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    strategy: RecoveryStrategy
    priority: int = Field(ge=0)
    allowed_failure_categories: list[
        RetryFailureCategory
    ] = Field(default_factory=list)
    minimum_partial_quality_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    maximum_cache_age_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    enabled: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        """Validate strategy-specific configuration."""

        if len(set(self.allowed_failure_categories)) != len(
            self.allowed_failure_categories
        ):
            raise ValueError(
                "allowed_failure_categories must not "
                "contain duplicates"
            )

        if (
            self.strategy is RecoveryStrategy.PARTIAL_RESULT
            and self.minimum_partial_quality_score is None
        ):
            raise ValueError(
                "partial_result strategy requires "
                "minimum_partial_quality_score"
            )

        if (
            self.strategy is not RecoveryStrategy.PARTIAL_RESULT
            and self.minimum_partial_quality_score is not None
        ):
            raise ValueError(
                "minimum_partial_quality_score is only valid "
                "for partial_result strategy"
            )

        if (
            self.strategy is RecoveryStrategy.CACHED_RESULT
            and self.maximum_cache_age_seconds is None
        ):
            raise ValueError(
                "cached_result strategy requires "
                "maximum_cache_age_seconds"
            )

        if (
            self.strategy is not RecoveryStrategy.CACHED_RESULT
            and self.maximum_cache_age_seconds is not None
        ):
            raise ValueError(
                "maximum_cache_age_seconds is only valid "
                "for cached_result strategy"
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


class FailureRecoveryPolicy(BaseModel):
    """Versioned ordered recovery policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    policy_id: str
    name: str
    description: str
    version: str
    strategies: list[RecoveryStrategyRule] = Field(
        min_length=1
    )
    require_manual_review_before_abort: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        """Validate policy identity and strategy uniqueness."""

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

        strategy_values = [
            rule.strategy
            for rule in self.strategies
        ]

        if len(set(strategy_values)) != len(strategy_values):
            raise ValueError(
                "recovery strategies must be unique"
            )

        priorities = [
            rule.priority
            for rule in self.strategies
        ]

        if len(set(priorities)) != len(priorities):
            raise ValueError(
                "recovery strategy priorities must be unique"
            )

        if (
            self.require_manual_review_before_abort
            and RecoveryStrategy.MANUAL_REVIEW
            not in strategy_values
        ):
            raise ValueError(
                "manual review requirement needs "
                "manual_review strategy"
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
    def enabled_strategies(
        self,
    ) -> list[RecoveryStrategyRule]:
        """Return enabled strategies ordered by priority."""

        return sorted(
            (
                rule
                for rule in self.strategies
                if rule.enabled
            ),
            key=lambda rule: rule.priority,
        )


def default_failure_recovery_policy(
) -> FailureRecoveryPolicy:
    """Return the default AIRA recovery policy."""

    return FailureRecoveryPolicy(
        policy_id="aira-failure-recovery-v1",
        name="AIRA Failure Recovery Policy",
        description=(
            "Recover temporary execution failures using "
            "alternate resources and safe degradation."
        ),
        version="1.0.0",
        strategies=[
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ALTERNATE_TOOL,
                priority=10,
                allowed_failure_categories=[
                    RetryFailureCategory.TOOL_TEMPORARY,
                    RetryFailureCategory.NETWORK,
                    RetryFailureCategory
                    .SERVICE_UNAVAILABLE,
                ],
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ALTERNATE_AGENT,
                priority=20,
                allowed_failure_categories=[
                    RetryFailureCategory.TIMEOUT,
                    RetryFailureCategory.INTERNAL,
                    RetryFailureCategory.TOOL_TEMPORARY,
                ],
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.CACHED_RESULT,
                priority=30,
                allowed_failure_categories=[
                    RetryFailureCategory.NETWORK,
                    RetryFailureCategory.RATE_LIMIT,
                    RetryFailureCategory
                    .SERVICE_UNAVAILABLE,
                ],
                maximum_cache_age_seconds=3600.0,
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.PARTIAL_RESULT,
                priority=40,
                minimum_partial_quality_score=0.7,
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.MANUAL_REVIEW,
                priority=50,
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ABORT,
                priority=60,
            ),
        ],
        require_manual_review_before_abort=True,
    )
