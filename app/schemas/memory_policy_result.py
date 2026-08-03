"""Schemas for deterministic memory-storage policy decisions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class MemoryPolicyDecision(StrEnum):
    """Possible outcomes of a memory-storage policy check."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    REJECT = "reject"


class MemoryPolicyReason(StrEnum):
    """Stable reason codes for memory policy decisions."""

    ALLOWED = "allowed"
    WORKING_MEMORY_REQUIRES_EXPIRATION = (
        "working_memory_requires_expiration"
    )
    SESSION_MEMORY_REQUIRES_EXPIRATION = (
        "session_memory_requires_expiration"
    )
    LOW_IMPORTANCE = "low_importance"
    LOW_CONFIDENCE_INFERENCE = "low_confidence_inference"
    INFERENCE_REQUIRES_APPROVAL = (
        "inference_requires_approval"
    )
    SENSITIVE_CONTENT = "sensitive_content"
    SECRET_CONTENT = "secret_content"
    SOURCE_REFERENCE_REQUIRED = (
        "source_reference_required"
    )


class MemoryPolicyResult(BaseModel):
    """Structured result of one memory-storage policy check."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    decision: MemoryPolicyDecision
    reasons: list[MemoryPolicyReason] = Field(
        min_length=1
    )
    safe_message: str = Field(min_length=1)
    requires_user_approval: bool

    @model_validator(mode="after")
    def validate_result(self) -> MemoryPolicyResult:
        """Validate decision and approval consistency."""

        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError(
                "memory policy reasons must be unique"
            )

        if not self.safe_message.strip():
            raise ValueError(
                "memory policy safe_message must not be blank"
            )

        expected_approval = (
            self.decision
            is MemoryPolicyDecision.REQUIRE_APPROVAL
        )

        if self.requires_user_approval != expected_approval:
            raise ValueError(
                "requires_user_approval is inconsistent"
            )

        if (
            self.decision is MemoryPolicyDecision.ALLOW
            and self.reasons != [MemoryPolicyReason.ALLOWED]
        ):
            raise ValueError(
                "allowed decision requires only allowed reason"
            )

        if (
            self.decision is not MemoryPolicyDecision.ALLOW
            and MemoryPolicyReason.ALLOWED in self.reasons
        ):
            raise ValueError(
                "non-allowed decision must not contain allowed reason"
            )

        return self
