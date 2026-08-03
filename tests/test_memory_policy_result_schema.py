"""Tests for memory-policy result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.memory_policy_result import (
    MemoryPolicyDecision,
    MemoryPolicyReason,
    MemoryPolicyResult,
)


def test_allow_result_accepts_allowed_reason() -> None:
    result = MemoryPolicyResult(
        decision=MemoryPolicyDecision.ALLOW,
        reasons=[MemoryPolicyReason.ALLOWED],
        safe_message="Memory may be stored.",
        requires_user_approval=False,
    )

    assert result.decision is MemoryPolicyDecision.ALLOW


def test_require_approval_sets_approval_flag() -> None:
    result = MemoryPolicyResult(
        decision=(
            MemoryPolicyDecision.REQUIRE_APPROVAL
        ),
        reasons=[
            MemoryPolicyReason
            .INFERENCE_REQUIRES_APPROVAL
        ],
        safe_message="Approval is required.",
        requires_user_approval=True,
    )

    assert result.requires_user_approval is True


def test_reject_cannot_require_approval() -> None:
    with pytest.raises(
        ValidationError,
        match="requires_user_approval is inconsistent",
    ):
        MemoryPolicyResult(
            decision=MemoryPolicyDecision.REJECT,
            reasons=[
                MemoryPolicyReason.SENSITIVE_CONTENT
            ],
            safe_message="Rejected.",
            requires_user_approval=True,
        )


def test_allow_rejects_other_reasons() -> None:
    with pytest.raises(
        ValidationError,
        match="requires only allowed reason",
    ):
        MemoryPolicyResult(
            decision=MemoryPolicyDecision.ALLOW,
            reasons=[
                MemoryPolicyReason.LOW_IMPORTANCE
            ],
            safe_message="Invalid result.",
            requires_user_approval=False,
        )


def test_reject_rejects_allowed_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain allowed reason",
    ):
        MemoryPolicyResult(
            decision=MemoryPolicyDecision.REJECT,
            reasons=[MemoryPolicyReason.ALLOWED],
            safe_message="Invalid result.",
            requires_user_approval=False,
        )
