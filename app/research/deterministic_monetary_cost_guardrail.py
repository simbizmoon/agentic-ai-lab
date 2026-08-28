"""Pure monetary budget guardrail over immutable cost-ledger snapshots."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.monetary_cost_budget import (
    CostBudgetDecision,
    CostBudgetReason,
    MonetaryCostBudgetRequest,
    MonetaryCostBudgetResult,
)
from app.schemas.provider_cost import CostKind


class MonetaryCostBudgetError(ValueError):
    """Raised when a ledger cannot be evaluated without currency guessing."""


class DeterministicMonetaryCostGuardrail:
    """Check one authority and currency without conversion or hidden approval."""

    @staticmethod
    def evaluate(request: MonetaryCostBudgetRequest) -> MonetaryCostBudgetResult:
        budget = request.budget
        basis = budget.basis.cost_kind
        relevant = []
        unavailable = []

        for entry in request.ledger.entries:
            cost = entry.cost_record
            if cost.cost_kind is CostKind.UNAVAILABLE:
                unavailable.append(cost)
            elif cost.cost_kind is basis:
                if cost.currency != budget.currency:
                    raise MonetaryCostBudgetError(
                        "ledger contains budget-basis cost in another currency"
                    )
                relevant.append(cost)

        proposed = request.proposed_cost
        proposed_increment = Decimal(0)
        checked = [cost.cost_record_id for cost in relevant]
        if proposed is not None:
            checked.append(proposed.cost_record_id)
            if proposed.cost_kind is CostKind.UNAVAILABLE:
                unavailable.append(proposed)
            elif proposed.cost_kind is basis:
                if proposed.amount is None:
                    raise MonetaryCostBudgetError(
                        "monetary proposed cost must contain an amount"
                    )
                proposed_increment = proposed.amount

        accumulated = sum(
            (cost.amount for cost in relevant if cost.amount is not None),
            start=Decimal(0),
        )
        projected = accumulated + proposed_increment
        maximum = budget.maximum_execution_cost
        overage = max(projected - maximum, Decimal(0))
        remaining = max(maximum - projected, Decimal(0))

        if unavailable and budget.require_complete_cost:
            decision = (
                CostBudgetDecision.HUMAN_APPROVAL_REQUIRED
                if request.human_approval_allowed
                else CostBudgetDecision.STOP
            )
            reason = CostBudgetReason.COST_UNAVAILABLE
        elif overage > 0:
            decision = DeterministicMonetaryCostGuardrail._over_budget_decision(request)
            reason = CostBudgetReason.PROJECTED_COST_EXCEEDS_LIMIT
        elif unavailable:
            decision = CostBudgetDecision.CONTINUE
            reason = CostBudgetReason.COST_UNAVAILABLE_ALLOWED
        else:
            decision = CostBudgetDecision.CONTINUE
            reason = CostBudgetReason.WITHIN_BUDGET

        return MonetaryCostBudgetResult(
            execution_id=request.ledger.execution_id,
            basis=budget.basis,
            currency=budget.currency,
            maximum_execution_cost=maximum,
            accumulated_cost=accumulated,
            proposed_increment=proposed_increment,
            projected_cost=projected,
            remaining_cost=remaining,
            overage_cost=overage,
            unavailable_cost_count=len(unavailable),
            cost_complete=not unavailable,
            checked_cost_record_ids=tuple(checked),
            decision=decision,
            reason=reason,
            budget_exceeded=overage > 0,
        )

    @staticmethod
    def _over_budget_decision(
        request: MonetaryCostBudgetRequest,
    ) -> CostBudgetDecision:
        if request.scope_reduction_available:
            return CostBudgetDecision.SCOPE_REDUCTION_REQUIRED
        if request.lower_cost_path_available:
            return CostBudgetDecision.LOWER_COST_PATH_REQUIRED
        if request.human_approval_allowed:
            return CostBudgetDecision.HUMAN_APPROVAL_REQUIRED
        return CostBudgetDecision.STOP
