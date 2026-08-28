"""Offline tests for unified usage collection and immutable cost ledgers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.research.deterministic_provider_cost_calculator import (
    DeterministicPriceRegistry,
    DeterministicProviderCostCalculator,
)
from app.research.unified_usage_cost_ledger import (
    ImmutableUsageCostLedger,
    UnifiedUsageCollector,
    UsageCollectionError,
)
from app.schemas.bounded_research_agent_loop import ResearchAgentLoopUsage
from app.schemas.provider_cost import (
    CostKind,
    ModelPriceEntry,
    PriceRate,
    UsageUnit,
)
from app.schemas.provider_cost_ledger import ExecutionUsageCostLedger
from app.schemas.research_search_budget import ResearchSearchUsage
from app.schemas.scholarly_provider import ScholarlyProviderUsage
from app.services.text_generation import TokenUsage

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _openai_event():
    return UnifiedUsageCollector.from_openai_tokens(
        TokenUsage(
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=40,
            reasoning_tokens=10,
            total_tokens=140,
        ),
        usage_event_id="usage-openai",
        execution_id="execution-001",
        stage_name="answer_generation",
        provider_name="OpenAI",
        model_name="fixture-model",
        operation="responses.create",
        observed_at=NOW,
        request_id="request-001",
        response_id="response-001",
    )


def _estimated_calculation():
    usage = _openai_event()
    price = ModelPriceEntry(
        price_entry_id="price-fixture",
        registry_version="fixture-v1",
        provider_name="OpenAI",
        model_name="fixture-model",
        operation="responses.create",
        effective_from=NOW.date(),
        source_reference="offline-test-fixture",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.TOTAL_TOKEN,
                unit_size=Decimal(100),
                rate_amount=Decimal("0.01"),
                currency="USD",
            ),
        ),
    )
    calculator = DeterministicProviderCostCalculator(
        DeterministicPriceRegistry((price,))
    )
    return calculator.calculate(usage, cost_record_id="cost-estimated")


def _quantity_map(event) -> dict[UsageUnit, Decimal]:
    return {item.unit: item.quantity for item in event.quantities}


def test_collects_exact_openai_token_usage_and_provider_identity() -> None:
    event = _openai_event()
    values = _quantity_map(event)
    assert values[UsageUnit.REQUEST] == Decimal(1)
    assert values[UsageUnit.INPUT_TOKEN] == Decimal(100)
    assert values[UsageUnit.CACHED_INPUT_TOKEN] == Decimal(20)
    assert values[UsageUnit.OUTPUT_TOKEN] == Decimal(40)
    assert values[UsageUnit.REASONING_TOKEN] == Decimal(10)
    assert values[UsageUnit.TOTAL_TOKEN] == Decimal(140)
    assert event.request_id == "request-001"
    assert event.response_id == "response-001"


def test_collects_search_calls_and_fractional_credits_without_calling_provider() -> (
    None
):
    event = UnifiedUsageCollector.from_search_usage(
        ResearchSearchUsage(
            provider_call_count=2,
            credit_used=1.25,
            latency_used_ms=300,
        ),
        usage_event_id="usage-search",
        execution_id="execution-001",
        stage_name="source_search",
        provider_name="FixtureSearch",
        operation="search",
        observed_at=NOW,
    )
    values = _quantity_map(event)
    assert values == {
        UsageUnit.REQUEST: Decimal(2),
        UsageUnit.SEARCH_CREDIT: Decimal("1.25"),
    }


def test_collects_scholarly_request_count_without_inventing_record_costs() -> None:
    event = UnifiedUsageCollector.from_scholarly_usage(
        ScholarlyProviderUsage(
            request_count=1,
            records_received=2,
            records_accepted=1,
            records_rejected=1,
            duration_ms=20.0,
        ),
        usage_event_id="usage-scholarly",
        execution_id="execution-001",
        stage_name="scholarly_search",
        provider_name="OpenAlex",
        operation="works.search",
        observed_at=NOW,
    )
    assert _quantity_map(event) == {UsageUnit.REQUEST: Decimal(1)}


def test_collects_agent_loop_resources_as_distinct_units() -> None:
    event = UnifiedUsageCollector.from_agent_loop_usage(
        ResearchAgentLoopUsage(
            rounds=2,
            tool_calls=3,
            provider_calls=4,
            recorded_tokens=500,
            elapsed_seconds=1.25,
            external_requests=2,
        ),
        usage_event_id="usage-loop",
        execution_id="execution-001",
        stage_name="agent_loop",
        observed_at=NOW,
    )
    values = _quantity_map(event)
    assert values[UsageUnit.AGENT_ROUND] == Decimal(2)
    assert values[UsageUnit.TOOL_CALL] == Decimal(3)
    assert values[UsageUnit.PROVIDER_CALL] == Decimal(4)
    assert values[UsageUnit.RECORDED_TOKEN] == Decimal(500)
    assert values[UsageUnit.EXTERNAL_REQUEST] == Decimal(2)
    assert values[UsageUnit.LOCAL_COMPUTE_SECOND] == Decimal("1.25")


def test_provider_reported_cost_preserves_decimal_and_source() -> None:
    cost = UnifiedUsageCollector.provider_reported_cost(
        _openai_event(),
        cost_record_id="cost-reported",
        amount_text="0.00140",
        currency="USD",
        source_reference="provider-response-meta",
        recorded_at=NOW,
    )
    assert cost.cost_kind is CostKind.PROVIDER_REPORTED
    assert cost.amount == Decimal("0.00140")
    assert cost.source_reference == "provider-response-meta"


@pytest.mark.parametrize("value", ["not-a-number", "NaN", "Infinity", "-1"])
def test_provider_reported_cost_rejects_invalid_values(value: str) -> None:
    with pytest.raises(UsageCollectionError):
        UnifiedUsageCollector.provider_reported_cost(
            _openai_event(),
            cost_record_id="cost-reported",
            amount_text=value,
            currency="USD",
            source_reference="provider-response-meta",
            recorded_at=NOW,
        )


def test_unavailable_and_not_applicable_cost_remain_distinct() -> None:
    event = _openai_event()
    unavailable = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="unknown", recorded_at=NOW
    )
    not_applicable = UnifiedUsageCollector.not_applicable_cost(
        event, cost_record_id="not-applicable", recorded_at=NOW
    )
    assert unavailable.cost_kind is CostKind.UNAVAILABLE
    assert not_applicable.cost_kind is CostKind.NOT_APPLICABLE
    assert unavailable.amount is None
    assert not_applicable.amount is None


def test_ledger_append_returns_new_snapshot_and_preserves_old_snapshot() -> None:
    empty = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="execution-001"
    )
    event = _openai_event()
    cost = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="unknown", recorded_at=NOW
    )
    updated = ImmutableUsageCostLedger.append(
        empty, usage_event=event, cost_record=cost
    )
    assert empty.entries == ()
    assert len(updated.entries) == 1
    assert updated.totals == ()


def test_ledger_keeps_estimated_and_provider_reported_totals_separate() -> None:
    ledger = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="execution-001"
    )
    calculation = _estimated_calculation()
    ledger = ImmutableUsageCostLedger.append_calculation(ledger, calculation)

    search = UnifiedUsageCollector.from_search_usage(
        ResearchSearchUsage(provider_call_count=1, credit_used=1.0),
        usage_event_id="usage-search",
        execution_id="execution-001",
        stage_name="search",
        provider_name="FixtureSearch",
        operation="search",
        observed_at=NOW,
    )
    reported = UnifiedUsageCollector.provider_reported_cost(
        search,
        cost_record_id="cost-reported",
        amount_text="0.002",
        currency="USD",
        source_reference="provider-response-meta",
        recorded_at=NOW,
    )
    ledger = ImmutableUsageCostLedger.append(
        ledger, usage_event=search, cost_record=reported
    )
    totals = {(item.cost_kind, item.currency): item.amount for item in ledger.totals}
    assert totals[(CostKind.ESTIMATED, "USD")] == Decimal("0.014")
    assert totals[(CostKind.PROVIDER_REPORTED, "USD")] == Decimal("0.002")
    assert len(totals) == 2


def test_ledger_groups_currencies_without_conversion() -> None:
    ledger = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="execution-001"
    )
    first = _openai_event()
    first_cost = UnifiedUsageCollector.provider_reported_cost(
        first,
        cost_record_id="usd-cost",
        amount_text="1",
        currency="USD",
        source_reference="fixture",
        recorded_at=NOW,
    )
    ledger = ImmutableUsageCostLedger.append(
        ledger, usage_event=first, cost_record=first_cost
    )
    second = first.model_copy(
        update={"usage_event_id": "usage-krw", "provider_name": "Other"}
    )
    second_cost = UnifiedUsageCollector.provider_reported_cost(
        second,
        cost_record_id="krw-cost",
        amount_text="1000",
        currency="KRW",
        source_reference="fixture",
        recorded_at=NOW,
    )
    ledger = ImmutableUsageCostLedger.append(
        ledger, usage_event=second, cost_record=second_cost
    )
    assert {(item.currency, item.amount) for item in ledger.totals} == {
        ("USD", Decimal(1)),
        ("KRW", Decimal(1000)),
    }


def test_ledger_rejects_duplicate_usage_or_cost_identity() -> None:
    ledger = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="execution-001"
    )
    event = _openai_event()
    cost = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="cost-001", recorded_at=NOW
    )
    ledger = ImmutableUsageCostLedger.append(
        ledger, usage_event=event, cost_record=cost
    )
    with pytest.raises(ValidationError, match="usage event IDs must be unique"):
        ImmutableUsageCostLedger.append(ledger, usage_event=event, cost_record=cost)


def test_ledger_rejects_cross_execution_entry() -> None:
    ledger = ImmutableUsageCostLedger.empty(
        ledger_id="ledger-001", execution_id="other-execution"
    )
    event = _openai_event()
    cost = UnifiedUsageCollector.unavailable_cost(
        event, cost_record_id="cost-001", recorded_at=NOW
    )
    with pytest.raises(ValidationError, match="belong to the execution"):
        ImmutableUsageCostLedger.append(ledger, usage_event=event, cost_record=cost)


def test_ledger_json_round_trip_preserves_entries_and_totals() -> None:
    ledger = ImmutableUsageCostLedger.append_calculation(
        ImmutableUsageCostLedger.empty(
            ledger_id="ledger-001", execution_id="execution-001"
        ),
        _estimated_calculation(),
    )
    restored = ExecutionUsageCostLedger.model_validate_json(ledger.model_dump_json())
    assert restored == ledger
