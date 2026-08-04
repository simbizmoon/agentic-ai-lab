"""Deterministic failure recovery and fallback evaluation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.guardrails.failure_recovery import (
    FailureRecoveryContext,
    FailureRecoveryDecision,
    RecoveryCandidate,
    RecoveryDecisionStatus,
)
from app.guardrails.failure_recovery_evaluator_error import (
    FailureRecoveryEvaluatorError,
)
from app.guardrails.failure_recovery_policy import (
    FailureRecoveryPolicy,
    RecoveryStrategy,
    RecoveryStrategyRule,
    RecoveryTargetType,
)


class FailureRecoveryEvaluator:
    """Select the first usable recovery strategy."""

    def __init__(
        self,
        *,
        policy: FailureRecoveryPolicy,
        decision_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._policy = policy
        self._decision_id_factory = (
            decision_id_factory
            or (lambda: f"recovery-decision-{uuid4()}")
        )

    def evaluate(
        self,
        context: FailureRecoveryContext,
    ) -> FailureRecoveryDecision:
        """Evaluate recovery strategies in priority order."""

        if not context.retry_exhausted:
            raise FailureRecoveryEvaluatorError(
                "failure recovery requires exhausted retries"
            )

        for rule in self._policy.enabled_strategies:
            if (
                rule.allowed_failure_categories
                and context.failure_category
                not in rule.allowed_failure_categories
            ):
                continue

            decision = self._evaluate_rule(
                rule=rule,
                context=context,
            )

            if decision is not None:
                return decision

        raise FailureRecoveryEvaluatorError(
            "no applicable recovery strategy was found"
        )

    def _evaluate_rule(
        self,
        *,
        rule: RecoveryStrategyRule,
        context: FailureRecoveryContext,
    ) -> FailureRecoveryDecision | None:
        """Evaluate one ordered recovery strategy."""

        if rule.strategy is RecoveryStrategy.ALTERNATE_TOOL:
            candidate = self._first_candidate(
                context=context,
                target_type=RecoveryTargetType.TOOL,
                excluded_id=context.current_tool_name,
            )
            return self._candidate_decision(
                context=context,
                rule=rule,
                candidate=candidate,
            )

        if rule.strategy is RecoveryStrategy.ALTERNATE_AGENT:
            candidate = self._first_candidate(
                context=context,
                target_type=RecoveryTargetType.AGENT,
                excluded_id=context.current_agent_id,
            )
            return self._candidate_decision(
                context=context,
                rule=rule,
                candidate=candidate,
            )

        if rule.strategy is RecoveryStrategy.CACHED_RESULT:
            candidate = self._cache_candidate(
                context=context,
                maximum_age=rule.maximum_cache_age_seconds,
            )
            return self._candidate_decision(
                context=context,
                rule=rule,
                candidate=candidate,
            )

        if rule.strategy is RecoveryStrategy.PARTIAL_RESULT:
            candidate = self._partial_candidate(
                context=context,
                minimum_quality=(
                    rule.minimum_partial_quality_score
                ),
            )
            return self._candidate_decision(
                context=context,
                rule=rule,
                candidate=candidate,
            )

        if rule.strategy is RecoveryStrategy.MANUAL_REVIEW:
            return self._terminal_decision(
                context=context,
                status=RecoveryDecisionStatus.REVIEW,
                strategy=RecoveryStrategy.MANUAL_REVIEW,
                target_type=RecoveryTargetType.HUMAN,
            )

        if rule.strategy is RecoveryStrategy.ABORT:
            return self._terminal_decision(
                context=context,
                status=RecoveryDecisionStatus.ABORT,
                strategy=RecoveryStrategy.ABORT,
                target_type=RecoveryTargetType.NONE,
            )

        return None

    def _candidate_decision(
        self,
        *,
        context: FailureRecoveryContext,
        rule: RecoveryStrategyRule,
        candidate: RecoveryCandidate | None,
    ) -> FailureRecoveryDecision | None:
        """Build a recovery decision when a candidate exists."""

        if candidate is None:
            return None

        return FailureRecoveryDecision(
            decision_id=self._new_identifier(),
            policy_id=self._policy.policy_id,
            failure_id=context.failure_id,
            status=RecoveryDecisionStatus.RECOVER,
            strategy=rule.strategy,
            target_type=candidate.target_type,
            selected_candidate_id=candidate.candidate_id,
            summary=(
                "Failure recovery selected "
                f"{rule.strategy.value} using "
                f"{candidate.candidate_id}."
            ),
            metadata={
                "failure_category": (
                    context.failure_category.value
                ),
                "error_code": context.error_code,
            },
        )

    def _terminal_decision(
        self,
        *,
        context: FailureRecoveryContext,
        status: RecoveryDecisionStatus,
        strategy: RecoveryStrategy,
        target_type: RecoveryTargetType,
    ) -> FailureRecoveryDecision:
        """Build manual-review or abort decision."""

        return FailureRecoveryDecision(
            decision_id=self._new_identifier(),
            policy_id=self._policy.policy_id,
            failure_id=context.failure_id,
            status=status,
            strategy=strategy,
            target_type=target_type,
            summary=(
                "Failure recovery selected "
                f"{strategy.value}."
            ),
            metadata={
                "failure_category": (
                    context.failure_category.value
                ),
                "error_code": context.error_code,
            },
        )

    @staticmethod
    def _first_candidate(
        *,
        context: FailureRecoveryContext,
        target_type: RecoveryTargetType,
        excluded_id: str | None,
    ) -> RecoveryCandidate | None:
        """Return the highest-priority usable candidate."""

        normalized_excluded = (
            excluded_id.strip().casefold()
            if excluded_id is not None
            else None
        )

        candidates = [
            candidate
            for candidate in context.candidates
            if (
                candidate.available
                and candidate.target_type is target_type
                and candidate.candidate_id
                .strip()
                .casefold()
                != normalized_excluded
            )
        ]

        return min(
            candidates,
            key=lambda candidate: (
                candidate.priority,
                candidate.candidate_id.casefold(),
            ),
            default=None,
        )

    @staticmethod
    def _cache_candidate(
        *,
        context: FailureRecoveryContext,
        maximum_age: float | None,
    ) -> RecoveryCandidate | None:
        """Return the freshest valid cache candidate."""

        if maximum_age is None:
            return None

        candidates = [
            candidate
            for candidate in context.candidates
            if (
                candidate.available
                and candidate.target_type
                is RecoveryTargetType.CACHE
                and candidate.age_seconds is not None
                and candidate.age_seconds <= maximum_age
            )
        ]

        return min(
            candidates,
            key=lambda candidate: (
                candidate.age_seconds
                if candidate.age_seconds is not None
                else float("inf"),
                candidate.priority,
            ),
            default=None,
        )

    @staticmethod
    def _partial_candidate(
        *,
        context: FailureRecoveryContext,
        minimum_quality: float | None,
    ) -> RecoveryCandidate | None:
        """Return the highest-quality valid partial output."""

        if minimum_quality is None:
            return None

        candidates = [
            candidate
            for candidate in context.candidates
            if (
                candidate.available
                and candidate.target_type
                is RecoveryTargetType.PARTIAL_OUTPUT
                and candidate.quality_score is not None
                and candidate.quality_score >= minimum_quality
            )
        ]

        return max(
            candidates,
            key=lambda candidate: (
                candidate.quality_score
                if candidate.quality_score is not None
                else 0.0,
                -candidate.priority,
            ),
            default=None,
        )

    def _new_identifier(self) -> str:
        """Generate one nonblank decision identifier."""

        value = self._decision_id_factory()

        if not value.strip():
            raise FailureRecoveryEvaluatorError(
                "decision_id factory returned blank value"
            )

        return value
