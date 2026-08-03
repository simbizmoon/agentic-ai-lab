"""Configuration for deterministic memory-storage policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MemoryPolicyConfig(BaseModel):
    """Thresholds and switches used by memory policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    minimum_importance: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
    )
    minimum_inference_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
    )
    inferred_memory_requires_approval: bool = True
    reject_sensitive_content: bool = True
    require_expiration_for_working_memory: bool = True
    require_expiration_for_session_scope: bool = True
