"""Tests for deterministic memory-storage policy."""

from datetime import UTC, datetime, timedelta

from app.memory.memory_policy import MemoryPolicy
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_policy_config import (
    MemoryPolicyConfig,
)
from app.schemas.memory_policy_result import (
    MemoryPolicyDecision,
    MemoryPolicyReason,
)
from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
    MemorySource,
)

NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)


def request(
    **overrides: object,
) -> MemoryCreate:
    """Return one valid memory-policy request."""

    values: dict[str, object] = {
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "importance": 0.8,
        "confidence": 1.0,
    }
    values.update(overrides)

    return MemoryCreate(**values)


def test_allows_direct_high_value_user_statement() -> None:
    result = MemoryPolicy().evaluate(request())

    assert result.decision is MemoryPolicyDecision.ALLOW
    assert result.reasons == [
        MemoryPolicyReason.ALLOWED
    ]


def test_rejects_low_importance_memory() -> None:
    result = MemoryPolicy().evaluate(
        request(importance=0.1)
    )

    assert result.decision is MemoryPolicyDecision.REJECT
    assert MemoryPolicyReason.LOW_IMPORTANCE in (
        result.reasons
    )


def test_working_memory_requires_expiration() -> None:
    result = MemoryPolicy().evaluate(
        request(
            kind=MemoryKind.WORKING,
            scope=MemoryScope.SESSION,
            subject_id=None,
            session_id="session-001",
        )
    )

    assert result.decision is MemoryPolicyDecision.REJECT
    assert (
        MemoryPolicyReason
        .WORKING_MEMORY_REQUIRES_EXPIRATION
        in result.reasons
    )
    assert (
        MemoryPolicyReason
        .SESSION_MEMORY_REQUIRES_EXPIRATION
        in result.reasons
    )


def test_working_memory_with_expiration_is_allowed() -> None:
    result = MemoryPolicy().evaluate(
        request(
            kind=MemoryKind.WORKING,
            scope=MemoryScope.SESSION,
            subject_id=None,
            session_id="session-001",
            expires_at=NOW + timedelta(hours=1),
        )
    )

    assert result.decision is MemoryPolicyDecision.ALLOW


def test_inference_requires_approval() -> None:
    result = MemoryPolicy().evaluate(
        request(
            source=MemorySource.AGENT_INFERENCE,
            source_reference="conversation-turn-123",
            confidence=0.9,
        )
    )

    assert result.decision is (
        MemoryPolicyDecision.REQUIRE_APPROVAL
    )
    assert result.requires_user_approval is True


def test_low_confidence_inference_is_rejected() -> None:
    result = MemoryPolicy().evaluate(
        request(
            source=MemorySource.AGENT_INFERENCE,
            source_reference="conversation-turn-123",
            confidence=0.5,
        )
    )

    assert result.decision is MemoryPolicyDecision.REJECT
    assert (
        MemoryPolicyReason.LOW_CONFIDENCE_INFERENCE
        in result.reasons
    )


def test_rejects_secret_content() -> None:
    result = MemoryPolicy().evaluate(
        request(
            content=(
                "The API key is "
                "sk-abcdefghijklmnopqrstuv."
            )
        )
    )

    assert result.decision is MemoryPolicyDecision.REJECT
    assert MemoryPolicyReason.SECRET_CONTENT in (
        result.reasons
    )


def test_rejects_sensitive_identifier() -> None:
    result = MemoryPolicy().evaluate(
        request(
            content=(
                "주민등록번호는 "
                "900101-1234567입니다."
            )
        )
    )

    assert result.decision is MemoryPolicyDecision.REJECT
    assert MemoryPolicyReason.SENSITIVE_CONTENT in (
        result.reasons
    )


def test_sensitive_rejection_can_be_disabled() -> None:
    policy = MemoryPolicy(
        config=MemoryPolicyConfig(
            reject_sensitive_content=False
        )
    )

    result = policy.evaluate(
        request(
            content=(
                "주민등록번호는 "
                "900101-1234567입니다."
            )
        )
    )

    assert result.decision is MemoryPolicyDecision.ALLOW


def test_inference_approval_can_be_disabled() -> None:
    policy = MemoryPolicy(
        config=MemoryPolicyConfig(
            inferred_memory_requires_approval=False
        )
    )

    result = policy.evaluate(
        request(
            source=MemorySource.AGENT_INFERENCE,
            source_reference="conversation-turn-123",
            confidence=0.9,
        )
    )

    assert result.decision is MemoryPolicyDecision.ALLOW
