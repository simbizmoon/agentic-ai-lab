"""Tests for deterministic failure recovery evaluation."""

import pytest
from pydantic import ValidationError

from app.guardrails.failure_recovery import (
    FailureRecoveryContext,
    RecoveryCandidate,
    RecoveryDecisionStatus,
)
from app.guardrails.failure_recovery_evaluator import (
    FailureRecoveryEvaluator,
)
from app.guardrails.failure_recovery_evaluator_error import (
    FailureRecoveryEvaluatorError,
)
from app.guardrails.failure_recovery_policy import (
    FailureRecoveryPolicy,
    RecoveryStrategy,
    RecoveryStrategyRule,
    RecoveryTargetType,
    default_failure_recovery_policy,
)
from app.guardrails.retry_policy import RetryFailureCategory


def policy() -> FailureRecoveryPolicy:
    """Return one ordered recovery policy."""

    return FailureRecoveryPolicy(
        policy_id="recovery-policy-001",
        name="Test recovery policy",
        description="Recover failed test executions.",
        version="1.0.0",
        strategies=[
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ALTERNATE_TOOL,
                priority=10,
                allowed_failure_categories=[
                    RetryFailureCategory.TOOL_TEMPORARY,
                ],
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ALTERNATE_AGENT,
                priority=20,
            ),
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.CACHED_RESULT,
                priority=30,
                maximum_cache_age_seconds=300.0,
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


def candidate(
    *,
    candidate_id: str,
    target_type: RecoveryTargetType,
    available: bool = True,
    priority: int = 100,
    quality_score: float | None = None,
    age_seconds: float | None = None,
) -> RecoveryCandidate:
    """Return one recovery candidate."""

    return RecoveryCandidate(
        candidate_id=candidate_id,
        target_type=target_type,
        available=available,
        priority=priority,
        quality_score=quality_score,
        age_seconds=age_seconds,
    )


def context(
    *,
    category: RetryFailureCategory = (
        RetryFailureCategory.TOOL_TEMPORARY
    ),
    current_tool_name: str | None = "tool-primary",
    current_agent_id: str | None = "agent-primary",
    retry_exhausted: bool = True,
    candidates: list[RecoveryCandidate] | None = None,
) -> FailureRecoveryContext:
    """Return one recovery context."""

    return FailureRecoveryContext(
        failure_id="failure-001",
        failure_category=category,
        error_code="TEMPORARY_FAILURE",
        current_tool_name=current_tool_name,
        current_agent_id=current_agent_id,
        retry_exhausted=retry_exhausted,
        candidates=candidates or [],
    )


def evaluator() -> FailureRecoveryEvaluator:
    """Return one deterministic evaluator."""

    return FailureRecoveryEvaluator(
        policy=policy(),
        decision_id_factory=(
            lambda: "recovery-decision-001"
        ),
    )


def test_alternate_tool_is_selected_first() -> None:
    value = evaluator().evaluate(
        context(
            candidates=[
                candidate(
                    candidate_id="tool-secondary",
                    target_type=RecoveryTargetType.TOOL,
                    priority=10,
                ),
                candidate(
                    candidate_id="agent-secondary",
                    target_type=RecoveryTargetType.AGENT,
                    priority=1,
                ),
            ]
        )
    )

    assert value.status is RecoveryDecisionStatus.RECOVER
    assert value.strategy is RecoveryStrategy.ALTERNATE_TOOL
    assert value.selected_candidate_id == "tool-secondary"


def test_current_tool_is_not_selected_as_fallback() -> None:
    value = evaluator().evaluate(
        context(
            candidates=[
                candidate(
                    candidate_id="tool-primary",
                    target_type=RecoveryTargetType.TOOL,
                ),
                candidate(
                    candidate_id="agent-secondary",
                    target_type=RecoveryTargetType.AGENT,
                ),
            ]
        )
    )

    assert value.strategy is RecoveryStrategy.ALTERNATE_AGENT
    assert value.selected_candidate_id == "agent-secondary"


def test_unavailable_tool_is_skipped() -> None:
    value = evaluator().evaluate(
        context(
            candidates=[
                candidate(
                    candidate_id="tool-secondary",
                    target_type=RecoveryTargetType.TOOL,
                    available=False,
                ),
                candidate(
                    candidate_id="agent-secondary",
                    target_type=RecoveryTargetType.AGENT,
                ),
            ]
        )
    )

    assert value.strategy is RecoveryStrategy.ALTERNATE_AGENT


def test_strategy_category_filter_is_applied() -> None:
    value = evaluator().evaluate(
        context(
            category=RetryFailureCategory.TIMEOUT,
            candidates=[
                candidate(
                    candidate_id="tool-secondary",
                    target_type=RecoveryTargetType.TOOL,
                ),
                candidate(
                    candidate_id="agent-secondary",
                    target_type=RecoveryTargetType.AGENT,
                ),
            ],
        )
    )

    assert value.strategy is RecoveryStrategy.ALTERNATE_AGENT


def test_valid_cache_is_selected() -> None:
    value = evaluator().evaluate(
        context(
            category=RetryFailureCategory.NETWORK,
            candidates=[
                candidate(
                    candidate_id="cache-old",
                    target_type=RecoveryTargetType.CACHE,
                    age_seconds=500.0,
                ),
                candidate(
                    candidate_id="cache-fresh",
                    target_type=RecoveryTargetType.CACHE,
                    age_seconds=100.0,
                ),
            ],
        )
    )

    assert value.strategy is RecoveryStrategy.CACHED_RESULT
    assert value.selected_candidate_id == "cache-fresh"


def test_expired_cache_is_skipped() -> None:
    value = evaluator().evaluate(
        context(
            category=RetryFailureCategory.NETWORK,
            candidates=[
                candidate(
                    candidate_id="cache-old",
                    target_type=RecoveryTargetType.CACHE,
                    age_seconds=500.0,
                )
            ],
        )
    )

    assert value.strategy is RecoveryStrategy.MANUAL_REVIEW


def test_high_quality_partial_result_is_selected() -> None:
    value = evaluator().evaluate(
        context(
            category=RetryFailureCategory.INTERNAL,
            candidates=[
                candidate(
                    candidate_id="partial-low",
                    target_type=(
                        RecoveryTargetType.PARTIAL_OUTPUT
                    ),
                    quality_score=0.6,
                ),
                candidate(
                    candidate_id="partial-good",
                    target_type=(
                        RecoveryTargetType.PARTIAL_OUTPUT
                    ),
                    quality_score=0.85,
                ),
            ],
        )
    )

    assert value.strategy is RecoveryStrategy.PARTIAL_RESULT
    assert value.selected_candidate_id == "partial-good"


def test_low_quality_partial_result_is_skipped() -> None:
    value = evaluator().evaluate(
        context(
            category=RetryFailureCategory.INTERNAL,
            candidates=[
                candidate(
                    candidate_id="partial-low",
                    target_type=(
                        RecoveryTargetType.PARTIAL_OUTPUT
                    ),
                    quality_score=0.5,
                )
            ],
        )
    )

    assert value.status is RecoveryDecisionStatus.REVIEW
    assert value.strategy is RecoveryStrategy.MANUAL_REVIEW


def test_manual_review_is_used_when_no_fallback_exists() -> None:
    value = evaluator().evaluate(context())

    assert value.status is RecoveryDecisionStatus.REVIEW
    assert value.target_type is RecoveryTargetType.HUMAN


def test_abort_is_used_without_manual_review_strategy() -> None:
    abort_policy = FailureRecoveryPolicy(
        policy_id="abort-policy",
        name="Abort policy",
        description="Abort when no recovery is possible.",
        version="1.0.0",
        strategies=[
            RecoveryStrategyRule(
                strategy=RecoveryStrategy.ABORT,
                priority=10,
            )
        ],
    )

    value = FailureRecoveryEvaluator(
        policy=abort_policy,
        decision_id_factory=lambda: "decision-abort",
    ).evaluate(context())

    assert value.status is RecoveryDecisionStatus.ABORT
    assert value.strategy is RecoveryStrategy.ABORT


def test_recovery_requires_exhausted_retries() -> None:
    with pytest.raises(
        FailureRecoveryEvaluatorError,
        match="failure recovery requires exhausted retries",
    ):
        evaluator().evaluate(
            context(retry_exhausted=False)
        )


def test_duplicate_candidate_ids_are_rejected() -> None:
    duplicate = candidate(
        candidate_id="candidate-001",
        target_type=RecoveryTargetType.AGENT,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "candidates must have unique candidate IDs"
        ),
    ):
        context(candidates=[duplicate, duplicate])


def test_partial_candidate_requires_quality_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "partial output candidate requires quality_score"
        ),
    ):
        candidate(
            candidate_id="partial-001",
            target_type=RecoveryTargetType.PARTIAL_OUTPUT,
        )


def test_cache_candidate_requires_age() -> None:
    with pytest.raises(
        ValidationError,
        match="cache candidate requires age_seconds",
    ):
        candidate(
            candidate_id="cache-001",
            target_type=RecoveryTargetType.CACHE,
        )


def test_policy_rejects_duplicate_strategies() -> None:
    duplicate = RecoveryStrategyRule(
        strategy=RecoveryStrategy.ABORT,
        priority=10,
    )

    with pytest.raises(
        ValidationError,
        match="recovery strategies must be unique",
    ):
        FailureRecoveryPolicy(
            policy_id="duplicate-policy",
            name="Duplicate policy",
            description="Contains duplicate strategies.",
            version="1.0.0",
            strategies=[
                duplicate,
                duplicate.model_copy(
                    update={"priority": 20}
                ),
            ],
        )


def test_default_policy_contains_safe_fallbacks() -> None:
    value = default_failure_recovery_policy()
    strategies = [
        rule.strategy
        for rule in value.enabled_strategies
    ]

    assert strategies[0] is RecoveryStrategy.ALTERNATE_TOOL
    assert RecoveryStrategy.MANUAL_REVIEW in strategies
    assert strategies[-1] is RecoveryStrategy.ABORT


def test_blank_decision_id_is_rejected() -> None:
    value = FailureRecoveryEvaluator(
        policy=policy(),
        decision_id_factory=lambda: " ",
    )

    with pytest.raises(
        FailureRecoveryEvaluatorError,
        match="decision_id factory returned blank value",
    ):
        value.evaluate(context())
