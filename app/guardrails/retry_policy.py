"""Schemas for deterministic retry and backoff policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RetryFailureCategory(StrEnum):
    """Normalized failure category used by retry policies."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    TOOL_TEMPORARY = "tool_temporary"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION = "validation"
    PERMISSION = "permission"
    POLICY = "policy"
    AUTHENTICATION = "authentication"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL = "internal"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class RetryBackoffStrategy(StrEnum):
    """Backoff strategy used between attempts."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class RetryJitterStrategy(StrEnum):
    """Jitter strategy applied to computed delays."""

    NONE = "none"
    FULL = "full"
    EQUAL = "equal"


class RetryPolicy(BaseModel):
    """Versioned retry and backoff policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    policy_id: str
    name: str
    description: str
    version: str
    maximum_attempts: int = Field(default=3, ge=1)
    base_delay_seconds: float = Field(default=1.0, ge=0)
    maximum_delay_seconds: float = Field(default=30.0, ge=0)
    backoff_strategy: RetryBackoffStrategy = (
        RetryBackoffStrategy.EXPONENTIAL
    )
    multiplier: float = Field(default=2.0, ge=1)
    jitter_strategy: RetryJitterStrategy = (
        RetryJitterStrategy.NONE
    )
    allowed_categories: list[RetryFailureCategory] = Field(
        default_factory=list
    )
    denied_categories: list[RetryFailureCategory] = Field(
        default_factory=list
    )
    allowed_error_codes: list[str] = Field(
        default_factory=list
    )
    denied_error_codes: list[str] = Field(
        default_factory=list
    )
    respect_retry_after: bool = True
    retry_after_max_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        """Validate retry policy consistency."""

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

        if self.maximum_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "maximum_delay_seconds must be greater than "
                "or equal to base_delay_seconds"
            )

        self._validate_unique_enum(
            self.allowed_categories,
            field_name="allowed_categories",
        )
        self._validate_unique_enum(
            self.denied_categories,
            field_name="denied_categories",
        )
        self._validate_unique_text(
            self.allowed_error_codes,
            field_name="allowed_error_codes",
        )
        self._validate_unique_text(
            self.denied_error_codes,
            field_name="denied_error_codes",
        )

        category_overlap = (
            set(self.allowed_categories)
            & set(self.denied_categories)
        )

        if category_overlap:
            raise ValueError(
                "allowed_categories and denied_categories "
                "must not overlap"
            )

        allowed_codes = {
            code.strip().casefold()
            for code in self.allowed_error_codes
        }
        denied_codes = {
            code.strip().casefold()
            for code in self.denied_error_codes
        }

        if allowed_codes & denied_codes:
            raise ValueError(
                "allowed_error_codes and denied_error_codes "
                "must not overlap"
            )

        if (
            self.retry_after_max_seconds is not None
            and not self.respect_retry_after
        ):
            raise ValueError(
                "retry_after_max_seconds requires "
                "respect_retry_after"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_enum(
        values: list[RetryFailureCategory],
        *,
        field_name: str,
    ) -> None:
        """Validate unique enum members."""

        if len(set(values)) != len(values):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank strings."""

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


def default_retry_policy() -> RetryPolicy:
    """Return the default AIRA retry policy."""

    return RetryPolicy(
        policy_id="aira-default-retry-v1",
        name="AIRA Default Retry Policy",
        description=(
            "Retry temporary infrastructure and tool failures "
            "while stopping deterministic client failures."
        ),
        version="1.0.0",
        maximum_attempts=3,
        base_delay_seconds=1.0,
        maximum_delay_seconds=30.0,
        backoff_strategy=RetryBackoffStrategy.EXPONENTIAL,
        multiplier=2.0,
        jitter_strategy=RetryJitterStrategy.EQUAL,
        allowed_categories=[
            RetryFailureCategory.TIMEOUT,
            RetryFailureCategory.RATE_LIMIT,
            RetryFailureCategory.NETWORK,
            RetryFailureCategory.TOOL_TEMPORARY,
            RetryFailureCategory.SERVICE_UNAVAILABLE,
        ],
        denied_categories=[
            RetryFailureCategory.VALIDATION,
            RetryFailureCategory.PERMISSION,
            RetryFailureCategory.POLICY,
            RetryFailureCategory.AUTHENTICATION,
            RetryFailureCategory.NOT_FOUND,
            RetryFailureCategory.CANCELLED,
        ],
        respect_retry_after=True,
        retry_after_max_seconds=120.0,
    )
