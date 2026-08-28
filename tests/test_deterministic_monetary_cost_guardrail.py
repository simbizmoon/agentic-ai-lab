"""Offline tests for deterministic monetary cost budget decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.research.deterministic_monetary_cost_guardrail import (
    DeterministicMonetaryCostGuardrail,
    MonetaryCostBudgetError,
)
from app.research.unified_usage_cost_ledger import (
    ImmutableUsageCostLedger,
    UnifiedUsageCollector,
)
from app.schemas.monetary_cost_budget import (
    CostBudgetBasis,
    CostBudgetDecision,
    CostBudgetReason,
    MonetaryCostBudget,
    MonetaryCostBudgetRequest,
    MonetaryCostBudgetResult,
)
from app.schemas.provider_cost import (
    CostKind,
    CostRecord,
    ProviderUsageEvent,
    UsageQuantity,
    UsageUnit,
    UsageValueKind,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _event(identifier: str, execution_id: str = "execution-001"):
    return ProviderUsageEvent(
        usage_event_id=f"usage-{identifier}",
        execution_id=execution_id,
        stage_name="answer_generation",
        provider_name="FixtureProvider",
        model_name="fixture-model",
        operation="generate",
        observed_at=NOW,
        value_kind=UsageValueKind.OBSERVED,
        quantities=(UsageQuantity(unit=UsageUnit.REQUEST, quantity=Decimal(1)),),
    )


def _cost(
    identifier: str,
    amount: str,
    *,
    kind: CostKind = CostKind.ESTIMATED,
    currency: str = "USD",
    execution_id: str = "execution-001",
) -> CostRecord:
    kwargs = {}
    if kind is CostKind.ESTIMATED:
        kwargs = {
            "price_entry_id": "price-fixture",
            "registry_version": "fixture-v1",
        }
    return CostRecord(
        cost_record_id=f"cost-{identifier}",
        execution_id=execution_id,
        usage_event_id=f"usage-{identifier}",
        cost_kind=kind,
        amount=Decimal(amount),
        currency=currency,
        source_reference="offline-test-fixture",
        recorded_at=NOW,
        **kwargs,
    )


def _ledger(*costs: CostRecord):
    ledger = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="execution-001"
    )
    for cost in costs:
        identifier = cost.cost_record_id.removeprefix("cost-")
        ledger = ImmutableUsageCostLedger.append(
            ledger,
            usage_event=_event(identifier),
            cost_record=cost,
        )
    return ledger


def _budget(
    maximum: str = "1.00",
    *,
    basis: CostBudgetBasis = CostBudgetBasis.ESTIMATED,
    currency: str = "USD",
    require_complete: bool = True,
) -> MonetaryCostBudget:
    return MonetaryCostBudget(
        basis=basis,
        currency=currency,
        maximum_execution_cost=Decimal(maximum),
        require_complete_cost=require_complete,
    )


def _request(
    *,
    ledger=None,
    budget=None,
    proposed=None,
    scope: bool = False,
    lower: bool = False,
    approval: bool = False,
) -> MonetaryCostBudgetRequest:
    return MonetaryCostBudgetRequest(
        ledger=ledger or _ledger(),
        budget=budget or _budget(),
        proposed_cost=proposed,
        scope_reduction_available=scope,
        lower_cost_path_available=lower,
        human_approval_allowed=approval,
    )


def test_within_budget_continues_with_exact_remaining_amount() -> None:
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(
            ledger=_ledger(_cost("existing", "0.25")),
            proposed=_cost("proposed", "0.50"),
        )
    )
    assert result.decision is CostBudgetDecision.CONTINUE
    assert result.reason is CostBudgetReason.WITHIN_BUDGET
    assert result.accumulated_cost == Decimal("0.25")
    assert result.proposed_increment == Decimal("0.50")
    assert result.projected_cost == Decimal("0.75")
    assert result.remaining_cost == Decimal("0.25")
    assert result.overage_cost == Decimal(0)
    assert result.budget_exceeded is False


def test_exact_ceiling_is_allowed() -> None:
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(proposed=_cost("proposed", "1.00"))
    )
    assert result.decision is CostBudgetDecision.CONTINUE
    assert result.remaining_cost == Decimal(0)


@pytest.mark.parametrize(
    ("scope", "lower", "approval", "expected"),
    [
        (True, True, True, CostBudgetDecision.SCOPE_REDUCTION_REQUIRED),
        (False, True, True, CostBudgetDecision.LOWER_COST_PATH_REQUIRED),
        (False, False, True, CostBudgetDecision.HUMAN_APPROVAL_REQUIRED),
        (False, False, False, CostBudgetDecision.STOP),
    ],
)
def test_over_budget_uses_deterministic_remediation_priority(
    scope: bool,
    lower: bool,
    approval: bool,
    expected: CostBudgetDecision,
) -> None:
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(
            proposed=_cost("proposed", "1.10"),
            scope=scope,
            lower=lower,
            approval=approval,
        )
    )
    assert result.decision is expected
    assert result.reason is CostBudgetReason.PROJECTED_COST_EXCEEDS_LIMIT
    assert result.overage_cost == Decimal("0.10")
    assert result.budget_exceeded is True


def test_approval_required_does_not_increase_or_pass_the_budget() -> None:
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(proposed=_cost("proposed", "2"), approval=True)
    )
    assert result.decision is CostBudgetDecision.HUMAN_APPROVAL_REQUIRED
    assert result.maximum_execution_cost == Decimal("1.00")
    assert result.budget_exceeded is True


def test_unavailable_cost_requires_approval_or_stop_when_completeness_required() -> (
    None
):
    event = _event("unknown")
    unavailable = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="cost-unknown", recorded_at=NOW
    )
    ledger = ImmutableUsageCostLedger.append(
        _ledger(), usage_event=event, cost_record=unavailable
    )
    approval = DeterministicMonetaryCostGuardrail.evaluate(
        _request(ledger=ledger, approval=True)
    )
    stopped = DeterministicMonetaryCostGuardrail.evaluate(_request(ledger=ledger))
    assert approval.decision is CostBudgetDecision.HUMAN_APPROVAL_REQUIRED
    assert stopped.decision is CostBudgetDecision.STOP
    assert approval.reason is CostBudgetReason.COST_UNAVAILABLE
    assert approval.unavailable_cost_count == 1
    assert approval.budget_exceeded is False


def test_policy_can_explicitly_ignore_unavailable_cost() -> None:
    event = _event("unknown")
    unavailable = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="cost-unknown", recorded_at=NOW
    )
    ledger = ImmutableUsageCostLedger.append(
        _ledger(), usage_event=event, cost_record=unavailable
    )
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(ledger=ledger, budget=_budget(require_complete=False))
    )
    assert result.decision is CostBudgetDecision.CONTINUE
    assert result.unavailable_cost_count == 1
    assert result.cost_complete is False
    assert result.reason is CostBudgetReason.COST_UNAVAILABLE_ALLOWED


def test_not_applicable_cost_does_not_block_complete_accounting() -> None:
    event = _event("local")
    not_applicable = UnifiedUsageCollector.not_applicable_cost(
        event, cost_record_id="cost-local", recorded_at=NOW
    )
    ledger = ImmutableUsageCostLedger.append(
        _ledger(), usage_event=event, cost_record=not_applicable
    )
    result = DeterministicMonetaryCostGuardrail.evaluate(_request(ledger=ledger))
    assert result.decision is CostBudgetDecision.CONTINUE
    assert result.unavailable_cost_count == 0


def test_budget_counts_only_selected_cost_authority() -> None:
    ledger = _ledger(
        _cost("estimated", "0.90"),
        _cost("reported", "0.20", kind=CostKind.PROVIDER_REPORTED),
        _cost("billed", "0.30", kind=CostKind.BILLED),
    )
    estimated = DeterministicMonetaryCostGuardrail.evaluate(
        _request(ledger=ledger, budget=_budget(basis=CostBudgetBasis.ESTIMATED))
    )
    reported = DeterministicMonetaryCostGuardrail.evaluate(
        _request(
            ledger=ledger,
            budget=_budget(basis=CostBudgetBasis.PROVIDER_REPORTED),
        )
    )
    billed = DeterministicMonetaryCostGuardrail.evaluate(
        _request(ledger=ledger, budget=_budget(basis=CostBudgetBasis.BILLED))
    )
    assert estimated.accumulated_cost == Decimal("0.90")
    assert reported.accumulated_cost == Decimal("0.20")
    assert billed.accumulated_cost == Decimal("0.30")


def test_guardrail_refuses_cross_currency_ledger_without_conversion() -> None:
    ledger = _ledger(_cost("krw", "1000", currency="KRW"))
    with pytest.raises(MonetaryCostBudgetError, match="another currency"):
        DeterministicMonetaryCostGuardrail.evaluate(_request(ledger=ledger))


def test_request_rejects_cross_currency_or_wrong_basis_proposal() -> None:
    with pytest.raises(ValidationError, match="currency must match"):
        _request(proposed=_cost("krw", "1000", currency="KRW"))
    with pytest.raises(ValidationError, match="kind must match"):
        _request(proposed=_cost("reported", "0.1", kind=CostKind.PROVIDER_REPORTED))


def test_zero_budget_allows_zero_but_blocks_positive_cost() -> None:
    zero = _budget("0")
    allowed = DeterministicMonetaryCostGuardrail.evaluate(
        _request(budget=zero, proposed=_cost("zero", "0"))
    )
    blocked = DeterministicMonetaryCostGuardrail.evaluate(
        _request(budget=zero, proposed=_cost("positive", "0.0001"))
    )
    assert allowed.decision is CostBudgetDecision.CONTINUE
    assert blocked.decision is CostBudgetDecision.STOP


def test_result_contract_rejects_inconsistent_arithmetic() -> None:
    valid = DeterministicMonetaryCostGuardrail.evaluate(
        _request(proposed=_cost("proposed", "0.5"))
    )
    data = valid.model_dump()
    data["projected_cost"] = Decimal("0.6")
    with pytest.raises(ValidationError, match="projected cost"):
        MonetaryCostBudgetResult(**data)


def test_result_json_round_trip_preserves_decision_and_decimal_values() -> None:
    result = DeterministicMonetaryCostGuardrail.evaluate(
        _request(proposed=_cost("proposed", "1.1"), lower=True)
    )
    restored = MonetaryCostBudgetResult.model_validate_json(result.model_dump_json())
    assert restored == result
