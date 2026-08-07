"""Schemas for bounded research search usage."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchSearchBudget(BaseModel):
    """Maximum provider resources allowed for one research run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    maximum_provider_calls: int = Field(ge=1)
    maximum_credits: float = Field(ge=0.0)
    maximum_latency_ms: int = Field(ge=0)
    default_credit_per_call: float = Field(
        default=1.0,
        ge=0.0,
    )


class ResearchSearchUsage(BaseModel):
    """Accumulated provider resources used by one research run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    provider_call_count: int = Field(default=0, ge=0)
    credit_used: float = Field(default=0.0, ge=0.0)
    latency_used_ms: int = Field(default=0, ge=0)
    unreported_credit_call_count: int = Field(
        default=0,
        ge=0,
    )
    blocked_query_count: int = Field(default=0, ge=0)
