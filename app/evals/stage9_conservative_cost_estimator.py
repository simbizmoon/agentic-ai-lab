"""Conservative cost upper bound for Stage 9 recorded-token usage."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.bounded_research_agent_loop import BoundedResearchAgentLoopResult
from app.schemas.provider_cost import UsageUnit
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9LockedBaselineExperiment,
)

TOKEN_UNITS = frozenset(
    {
        UsageUnit.INPUT_TOKEN,
        UsageUnit.CACHED_INPUT_TOKEN,
        UsageUnit.OUTPUT_TOKEN,
        UsageUnit.REASONING_TOKEN,
        UsageUnit.TOTAL_TOKEN,
        UsageUnit.RECORDED_TOKEN,
    }
)


class Stage9ConservativeCostEstimationError(ValueError):
    """The approved price stack cannot support a safe upper-bound estimate."""


class ConservativeStage9RecordedTokenCostEstimator:
    """Price every unclassified recorded token at the highest locked token rate."""

    def estimate(
        self,
        *,
        loop_result: BoundedResearchAgentLoopResult,
        experiment: Stage9LockedBaselineExperiment,
    ) -> Decimal:
        if not isinstance(loop_result, BoundedResearchAgentLoopResult):
            raise TypeError("loop_result must be a BoundedResearchAgentLoopResult")
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")

        priced_rates = [
            rate
            for component in experiment.runtime_stack.components
            for rate in component.price_entry.rates
            if rate.usage_unit in TOKEN_UNITS
        ]
        if not priced_rates:
            raise Stage9ConservativeCostEstimationError(
                "runtime stack has no token price"
            )
        currencies = {rate.currency for rate in priced_rates}
        if currencies != {experiment.plan.manifest.execution_budget.currency}:
            raise Stage9ConservativeCostEstimationError(
                "token prices do not match the locked budget currency"
            )

        per_token_rates = [rate.rate_amount / rate.unit_size for rate in priced_rates]
        if any(value < 0 or not value.is_finite() for value in per_token_rates):
            raise Stage9ConservativeCostEstimationError(
                "token price must be finite and nonnegative"
            )
        highest_per_token_rate = max(per_token_rates)
        return Decimal(loop_result.usage.recorded_tokens) * highest_per_token_rate
