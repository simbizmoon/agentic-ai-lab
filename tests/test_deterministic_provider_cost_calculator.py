"""Offline tests for effective-dated deterministic provider cost calculation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.research.deterministic_provider_cost_calculator import (
    CostCalculationError,
    DeterministicPriceRegistry,
    DeterministicProviderCostCalculator,
    PriceNotFoundError,
    PriceRegistryError,
)
from app.schemas.provider_cost import (
    CostKind,
    ModelPriceEntry,
    PriceRate,
    ProviderUsageEvent,
    UsageQuantity,
    UsageUnit,
    UsageValueKind,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _quantity(unit: UsageUnit, value: str) -> UsageQuantity:
    return UsageQuantity(unit=unit, quantity=Decimal(value))


def _usage(
    *,
    provider: str = "ExampleProvider",
    model: str | None = "example-model",
    operation: str = "generate",
    quantities: tuple[UsageQuantity, ...] | None = None,
    observed_at: datetime = NOW,
) -> ProviderUsageEvent:
    return ProviderUsageEvent(
        usage_event_id="usage-001",
        execution_id="execution-001",
        stage_name="answer_generation",
        provider_name=provider,
        model_name=model,
        operation=operation,
        request_id="request-001",
        response_id="response-001",
        observed_at=observed_at,
        value_kind=UsageValueKind.PROVIDER_REPORTED,
        quantities=quantities
        or (
            _quantity(UsageUnit.INPUT_TOKEN, "100"),
            _quantity(UsageUnit.CACHED_INPUT_TOKEN, "20"),
            _quantity(UsageUnit.OUTPUT_TOKEN, "40"),
            _quantity(UsageUnit.REASONING_TOKEN, "10"),
            _quantity(UsageUnit.TOTAL_TOKEN, "140"),
        ),
    )


def _rates(*units: UsageUnit, amount: str = "1") -> tuple[PriceRate, ...]:
    return tuple(
        PriceRate(
            usage_unit=unit,
            unit_size=Decimal(100),
            rate_amount=Decimal(amount),
            currency="USD",
        )
        for unit in units
    )


def _price(
    *,
    entry_id: str = "price-001",
    version: str = "fixture-v1",
    provider: str = "ExampleProvider",
    model: str | None = "example-model",
    operation: str = "generate",
    start: date = date(2026, 1, 1),
    through: date | None = None,
    rates: tuple[PriceRate, ...] | None = None,
) -> ModelPriceEntry:
    return ModelPriceEntry(
        price_entry_id=entry_id,
        registry_version=version,
        provider_name=provider,
        model_name=model,
        operation=operation,
        effective_from=start,
        effective_through=through,
        source_reference="offline-test-fixture",
        rates=rates
        or _rates(
            UsageUnit.INPUT_TOKEN,
            UsageUnit.CACHED_INPUT_TOKEN,
            UsageUnit.OUTPUT_TOKEN,
            UsageUnit.REASONING_TOKEN,
        ),
    )


def _calculator(*entries: ModelPriceEntry) -> DeterministicProviderCostCalculator:
    return DeterministicProviderCostCalculator(
        DeterministicPriceRegistry(entries or (_price(),))
    )


def test_calculator_avoids_cached_and_reasoning_double_charge() -> None:
    result = _calculator().calculate(_usage(), cost_record_id="cost-001")
    lines = {item.usage_unit: item for item in result.line_items}
    assert lines[UsageUnit.INPUT_TOKEN].observed_quantity == Decimal(100)
    assert lines[UsageUnit.INPUT_TOKEN].billable_quantity == Decimal(80)
    assert lines[UsageUnit.CACHED_INPUT_TOKEN].billable_quantity == Decimal(20)
    assert lines[UsageUnit.OUTPUT_TOKEN].observed_quantity == Decimal(40)
    assert lines[UsageUnit.OUTPUT_TOKEN].billable_quantity == Decimal(30)
    assert lines[UsageUnit.REASONING_TOKEN].billable_quantity == Decimal(10)
    assert result.cost_record.amount == Decimal("1.4")


def test_calculation_preserves_exact_price_and_usage_provenance() -> None:
    result = _calculator().calculate(_usage(), cost_record_id="cost-001")
    assert result.cost_record.cost_kind is CostKind.ESTIMATED
    assert result.cost_record.usage_event_id == "usage-001"
    assert result.cost_record.price_entry_id == "price-001"
    assert result.cost_record.registry_version == "fixture-v1"
    assert result.cost_record.source_reference == "offline-test-fixture"


def test_line_items_are_canonical_regardless_of_rate_order() -> None:
    price = _price(
        rates=_rates(
            UsageUnit.REASONING_TOKEN,
            UsageUnit.OUTPUT_TOKEN,
            UsageUnit.CACHED_INPUT_TOKEN,
            UsageUnit.INPUT_TOKEN,
        )
    )
    result = _calculator(price).calculate(_usage(), cost_record_id="cost-001")
    units = [item.usage_unit.value for item in result.line_items]
    assert units == sorted(units)


def test_registry_selects_exact_effective_period_boundaries() -> None:
    old = _price(
        entry_id="old",
        version="v1",
        start=date(2026, 1, 1),
        through=date(2026, 6, 30),
        rates=_rates(UsageUnit.TOTAL_TOKEN, amount="1"),
    )
    new = _price(
        entry_id="new",
        version="v2",
        start=date(2026, 7, 1),
        rates=_rates(UsageUnit.TOTAL_TOKEN, amount="2"),
    )
    calculator = _calculator(old, new)
    first = calculator.calculate(
        _usage(observed_at=datetime(2026, 6, 30, tzinfo=UTC)),
        cost_record_id="old-cost",
    )
    second = calculator.calculate(
        _usage(observed_at=datetime(2026, 7, 1, tzinfo=UTC)),
        cost_record_id="new-cost",
    )
    assert first.price_entry.price_entry_id == "old"
    assert second.price_entry.price_entry_id == "new"
    assert first.cost_record.amount == Decimal("1.4")
    assert second.cost_record.amount == Decimal("2.8")


def test_explicit_pricing_date_overrides_usage_date() -> None:
    old = _price(
        entry_id="old",
        start=date(2026, 1, 1),
        through=date(2026, 6, 30),
        rates=_rates(UsageUnit.TOTAL_TOKEN),
    )
    result = _calculator(old).calculate(
        _usage(),
        cost_record_id="cost-001",
        pricing_date=date(2026, 6, 30),
    )
    assert result.price_entry.price_entry_id == "old"


@pytest.mark.parametrize(
    ("provider", "model", "operation"),
    [
        ("OtherProvider", "example-model", "generate"),
        ("ExampleProvider", "other-model", "generate"),
        ("ExampleProvider", "example-model", "embed"),
    ],
)
def test_registry_refuses_nonexact_provider_model_or_operation(
    provider: str, model: str, operation: str
) -> None:
    with pytest.raises(PriceNotFoundError):
        _calculator().calculate(
            _usage(provider=provider, model=model, operation=operation),
            cost_record_id="cost-001",
        )


def test_registry_refuses_unknown_date_instead_of_using_latest_price() -> None:
    price = _price(start=date(2026, 8, 25))
    with pytest.raises(PriceNotFoundError):
        _calculator(price).calculate(_usage(), cost_record_id="cost-001")


def test_registry_rejects_duplicate_ids_and_overlapping_periods() -> None:
    with pytest.raises(PriceRegistryError, match="IDs must be unique"):
        DeterministicPriceRegistry((_price(), _price()))
    first = _price(entry_id="one", start=date(2026, 1, 1), through=date(2026, 8, 1))
    second = _price(entry_id="two", start=date(2026, 8, 1))
    with pytest.raises(PriceRegistryError, match="must not overlap"):
        DeterministicPriceRegistry((first, second))


def test_registry_rejects_period_after_open_ended_entry() -> None:
    first = _price(entry_id="one", start=date(2026, 1, 1))
    second = _price(entry_id="two", start=date(2026, 8, 1))
    with pytest.raises(PriceRegistryError, match="must be the last"):
        DeterministicPriceRegistry((first, second))


def test_calculator_rejects_total_and_component_rate_combination() -> None:
    price = _price(rates=_rates(UsageUnit.TOTAL_TOKEN, UsageUnit.INPUT_TOKEN))
    with pytest.raises(CostCalculationError, match="cannot be combined"):
        _calculator(price).calculate(_usage(), cost_record_id="cost-001")


@pytest.mark.parametrize(
    ("rates", "message"),
    [
        (_rates(UsageUnit.CACHED_INPUT_TOKEN), "requires an input"),
        (_rates(UsageUnit.REASONING_TOKEN), "requires an output"),
    ],
)
def test_calculator_rejects_child_rate_without_parent_rate(
    rates: tuple[PriceRate, ...], message: str
) -> None:
    with pytest.raises(CostCalculationError, match=message):
        _calculator(_price(rates=rates)).calculate(_usage(), cost_record_id="cost-001")


def test_calculator_rejects_priced_unit_missing_from_usage() -> None:
    price = _price(rates=_rates(UsageUnit.REQUEST))
    with pytest.raises(CostCalculationError, match="absent from event"):
        _calculator(price).calculate(_usage(), cost_record_id="cost-001")


def test_unpriced_observability_units_do_not_create_cost_lines() -> None:
    price = _price(rates=_rates(UsageUnit.TOTAL_TOKEN, amount="2"))
    result = _calculator(price).calculate(_usage(), cost_record_id="cost-001")
    assert len(result.line_items) == 1
    assert result.line_items[0].usage_unit is UsageUnit.TOTAL_TOKEN
    assert result.cost_record.amount == Decimal("2.8")


def test_zero_rate_is_a_real_zero_estimated_cost() -> None:
    local_price = _price(
        provider="Local",
        model="deterministic-test",
        rates=_rates(UsageUnit.TOTAL_TOKEN, amount="0"),
    )
    result = _calculator(local_price).calculate(
        _usage(provider="Local", model="deterministic-test"),
        cost_record_id="cost-zero",
    )
    assert result.cost_record.cost_kind is CostKind.ESTIMATED
    assert result.cost_record.amount == Decimal(0)
    assert result.cost_record.currency == "USD"


def test_fractional_search_credit_uses_exact_decimal_arithmetic() -> None:
    usage = _usage(
        model=None,
        operation="search",
        quantities=(_quantity(UsageUnit.SEARCH_CREDIT, "0.25"),),
    )
    price = _price(
        model=None,
        operation="search",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.SEARCH_CREDIT,
                unit_size=Decimal(1),
                rate_amount=Decimal("0.004"),
                currency="USD",
            ),
        ),
    )
    result = _calculator(price).calculate(usage, cost_record_id="search-cost")
    assert result.cost_record.amount == Decimal("0.00100")


def test_calculation_json_round_trip_preserves_exact_decimal_values() -> None:
    result = _calculator().calculate(_usage(), cost_record_id="cost-001")
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored == result
