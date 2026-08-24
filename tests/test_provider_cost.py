"""Offline tests for provider-neutral usage, price, and cost contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.provider_cost import (
    CostKind,
    CostRecord,
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


def _usage() -> ProviderUsageEvent:
    return ProviderUsageEvent(
        usage_event_id="usage-001",
        execution_id="execution-001",
        stage_name="claim_generation",
        provider_name="OpenAI",
        model_name="example-model",
        operation="responses.create",
        request_id="request-001",
        response_id="response-001",
        observed_at=NOW,
        value_kind=UsageValueKind.PROVIDER_REPORTED,
        quantities=(
            _quantity(UsageUnit.REQUEST, "1"),
            _quantity(UsageUnit.INPUT_TOKEN, "100"),
            _quantity(UsageUnit.CACHED_INPUT_TOKEN, "20"),
            _quantity(UsageUnit.OUTPUT_TOKEN, "30"),
            _quantity(UsageUnit.REASONING_TOKEN, "10"),
            _quantity(UsageUnit.TOTAL_TOKEN, "130"),
        ),
    )


def _price() -> ModelPriceEntry:
    return ModelPriceEntry(
        price_entry_id="price-001",
        registry_version="prices-2026-08-24-test",
        provider_name="ExampleProvider",
        model_name="example-model",
        operation="responses.create",
        effective_from=date(2026, 8, 24),
        source_reference="offline-test-fixture",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.INPUT_TOKEN,
                unit_size=Decimal(1000000),
                rate_amount=Decimal("1.25"),
                currency="USD",
            ),
            PriceRate(
                usage_unit=UsageUnit.OUTPUT_TOKEN,
                unit_size=Decimal(1000000),
                rate_amount=Decimal("5.00"),
                currency="USD",
            ),
        ),
    )


def _estimated(amount: str = "0.000275") -> CostRecord:
    return CostRecord(
        cost_record_id="cost-001",
        execution_id="execution-001",
        usage_event_id="usage-001",
        cost_kind=CostKind.ESTIMATED,
        amount=Decimal(amount),
        currency="USD",
        price_entry_id="price-001",
        registry_version="prices-2026-08-24-test",
        source_reference="offline-test-fixture",
        recorded_at=NOW,
    )


def test_usage_event_preserves_exact_provider_identity_and_token_breakdown() -> None:
    usage = _usage()
    assert usage.provider_name == "OpenAI"
    assert usage.request_id == "request-001"
    assert {item.unit: item.quantity for item in usage.quantities}[
        UsageUnit.CACHED_INPUT_TOKEN
    ] == Decimal(20)


@pytest.mark.parametrize(
    ("unit", "value"),
    [
        (UsageUnit.REQUEST, "0.5"),
        (UsageUnit.INPUT_TOKEN, "1.25"),
        (UsageUnit.EMBEDDING_TOKEN, "2.1"),
    ],
)
def test_integral_usage_units_reject_fractional_values(
    unit: UsageUnit, value: str
) -> None:
    with pytest.raises(ValidationError, match="must be an integer"):
        _quantity(unit, value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_usage_quantity_rejects_nonfinite_values(value: str) -> None:
    with pytest.raises(ValidationError):
        _quantity(UsageUnit.SEARCH_CREDIT, value)


def test_usage_event_rejects_duplicate_units() -> None:
    data = _usage().model_dump()
    data["quantities"] = (
        _quantity(UsageUnit.REQUEST, "1"),
        _quantity(UsageUnit.REQUEST, "2"),
    )
    with pytest.raises(ValidationError, match="units must be unique"):
        ProviderUsageEvent(**data)


def test_usage_event_rejects_partial_core_token_group() -> None:
    data = _usage().model_dump()
    data["quantities"] = (_quantity(UsageUnit.INPUT_TOKEN, "10"),)
    with pytest.raises(ValidationError, match="supplied together"):
        ProviderUsageEvent(**data)


def test_usage_event_rejects_inconsistent_total_tokens() -> None:
    data = _usage().model_dump()
    data["quantities"] = tuple(
        _quantity(item.unit, "999") if item.unit is UsageUnit.TOTAL_TOKEN else item
        for item in _usage().quantities
    )
    with pytest.raises(ValidationError, match="total tokens"):
        ProviderUsageEvent(**data)


@pytest.mark.parametrize(
    ("unit", "value", "message"),
    [
        (UsageUnit.CACHED_INPUT_TOKEN, "101", "cached input"),
        (UsageUnit.REASONING_TOKEN, "31", "reasoning tokens"),
    ],
)
def test_usage_event_rejects_invalid_token_subcounts(
    unit: UsageUnit, value: str, message: str
) -> None:
    data = _usage().model_dump()
    data["quantities"] = tuple(
        _quantity(item.unit, value) if item.unit is unit else item
        for item in _usage().quantities
    )
    with pytest.raises(ValidationError, match=message):
        ProviderUsageEvent(**data)


def test_usage_event_requires_timezone_aware_observation() -> None:
    data = _usage().model_dump()
    data["observed_at"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone-aware"):
        ProviderUsageEvent(**data)


def test_price_entry_preserves_version_date_source_and_decimal_rates() -> None:
    price = _price()
    assert price.registry_version == "prices-2026-08-24-test"
    assert price.effective_from == date(2026, 8, 24)
    assert price.rates[0].rate_amount == Decimal("1.25")


def test_price_rate_rejects_lowercase_currency() -> None:
    with pytest.raises(ValidationError):
        PriceRate(
            usage_unit=UsageUnit.REQUEST,
            unit_size=Decimal(1),
            rate_amount=Decimal("0.01"),
            currency="usd",
        )


def test_price_entry_rejects_duplicate_units_and_mixed_currencies() -> None:
    data = _price().model_dump()
    data["rates"] = (data["rates"][0], data["rates"][0])
    with pytest.raises(ValidationError, match="unique usage units"):
        ModelPriceEntry(**data)

    data = _price().model_dump()
    second = PriceRate(
        usage_unit=UsageUnit.OUTPUT_TOKEN,
        unit_size=Decimal(1000000),
        rate_amount=Decimal(5),
        currency="KRW",
    )
    data["rates"] = (data["rates"][0], second)
    with pytest.raises(ValidationError, match="exactly one currency"):
        ModelPriceEntry(**data)


def test_price_entry_rejects_reversed_effective_range() -> None:
    data = _price().model_dump()
    data["effective_through"] = date(2026, 8, 23)
    with pytest.raises(ValidationError, match="must not precede"):
        ModelPriceEntry(**data)


def test_estimated_cost_requires_complete_usage_and_price_provenance() -> None:
    assert _estimated().amount == Decimal("0.000275")
    data = _estimated().model_dump()
    data["registry_version"] = None
    with pytest.raises(ValidationError, match="complete price provenance"):
        CostRecord(**data)


@pytest.mark.parametrize("kind", [CostKind.PROVIDER_REPORTED, CostKind.BILLED])
def test_reported_and_billed_cost_require_source(kind: CostKind) -> None:
    with pytest.raises(ValidationError, match="requires source_reference"):
        CostRecord(
            cost_record_id="cost-002",
            execution_id="execution-001",
            cost_kind=kind,
            amount=Decimal("0.01"),
            currency="USD",
            recorded_at=NOW,
        )


def test_unknown_cost_is_distinct_from_a_real_zero_monetary_cost() -> None:
    unavailable = CostRecord(
        cost_record_id="cost-unavailable",
        execution_id="execution-001",
        cost_kind=CostKind.UNAVAILABLE,
        recorded_at=NOW,
    )
    actual_zero = _estimated("0")
    assert unavailable.amount is None
    assert unavailable.currency is None
    assert actual_zero.amount == Decimal(0)
    assert actual_zero.currency == "USD"


def test_not_applicable_cost_cannot_invent_zero_money() -> None:
    with pytest.raises(ValidationError, match="must not invent money values"):
        CostRecord(
            cost_record_id="cost-na",
            execution_id="execution-001",
            cost_kind=CostKind.NOT_APPLICABLE,
            amount=Decimal(0),
            currency="USD",
            recorded_at=NOW,
        )


def test_cost_record_rejects_nonfinite_amount_and_naive_time() -> None:
    data = _estimated().model_dump()
    data["amount"] = Decimal("NaN")
    with pytest.raises(ValidationError):
        CostRecord(**data)

    data = _estimated().model_dump()
    data["recorded_at"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone-aware"):
        CostRecord(**data)


def test_contracts_are_strict_frozen_and_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UsageQuantity(unit=UsageUnit.REQUEST, quantity=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        UsageQuantity(
            unit=UsageUnit.REQUEST,
            quantity=Decimal(1),
            invented=True,  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        _usage().provider_name = "changed"  # type: ignore[misc]


def test_json_round_trip_preserves_decimal_and_enum_meaning() -> None:
    restored = ProviderUsageEvent.model_validate_json(_usage().model_dump_json())
    assert restored == _usage()
    restored_price = ModelPriceEntry.model_validate_json(_price().model_dump_json())
    assert restored_price == _price()
    restored_cost = CostRecord.model_validate_json(_estimated().model_dump_json())
    assert restored_cost == _estimated()
