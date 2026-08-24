"""Pure effective-dated price lookup and deterministic cost calculation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from itertools import pairwise

from app.schemas.provider_cost import (
    CostKind,
    CostRecord,
    ModelPriceEntry,
    ProviderUsageEvent,
    UsageUnit,
)
from app.schemas.provider_cost_calculation import (
    CostCalculationLineItem,
    ProviderCostCalculation,
)


class PriceRegistryError(ValueError):
    """Base error for invalid or ambiguous price registries."""


class PriceNotFoundError(LookupError):
    """Raised when no exact effective price exists for one usage event."""


class CostCalculationError(ValueError):
    """Raised when a selected price cannot be applied without guessing."""


class DeterministicPriceRegistry:
    """Immutable exact-match registry with non-overlapping effective periods."""

    def __init__(self, entries: Iterable[ModelPriceEntry]) -> None:
        self._entries = tuple(entries)
        if not self._entries:
            raise PriceRegistryError("price registry must contain at least one entry")
        ids = [entry.price_entry_id.casefold() for entry in self._entries]
        if len(ids) != len(set(ids)):
            raise PriceRegistryError("price entry IDs must be unique")
        self._validate_nonoverlapping_periods()

    @property
    def entries(self) -> tuple[ModelPriceEntry, ...]:
        return self._entries

    def find(self, usage: ProviderUsageEvent, *, pricing_date: date) -> ModelPriceEntry:
        matches = [
            entry
            for entry in self._entries
            if self._identity(entry) == self._usage_identity(usage)
            and entry.effective_from <= pricing_date
            and (
                entry.effective_through is None
                or pricing_date <= entry.effective_through
            )
        ]
        if not matches:
            raise PriceNotFoundError(
                "no exact effective price for provider, model, operation, and date"
            )
        if len(matches) != 1:
            raise PriceRegistryError("effective price lookup is ambiguous")
        return matches[0]

    def _validate_nonoverlapping_periods(self) -> None:
        grouped: dict[tuple[str, str | None, str], list[ModelPriceEntry]] = {}
        for entry in self._entries:
            grouped.setdefault(self._identity(entry), []).append(entry)
        for values in grouped.values():
            ordered = sorted(values, key=lambda item: item.effective_from)
            for previous, current in pairwise(ordered):
                if previous.effective_through is None:
                    raise PriceRegistryError(
                        "open-ended price entry must be the last effective period"
                    )
                if current.effective_from <= previous.effective_through:
                    raise PriceRegistryError("price effective periods must not overlap")

    @staticmethod
    def _identity(entry: ModelPriceEntry) -> tuple[str, str | None, str]:
        return (
            entry.provider_name.casefold(),
            entry.model_name.casefold() if entry.model_name is not None else None,
            entry.operation.casefold(),
        )

    @staticmethod
    def _usage_identity(usage: ProviderUsageEvent) -> tuple[str, str | None, str]:
        return (
            usage.provider_name.casefold(),
            usage.model_name.casefold() if usage.model_name is not None else None,
            usage.operation.casefold(),
        )


class DeterministicProviderCostCalculator:
    """Apply one exact registry entry using Decimal arithmetic only."""

    def __init__(self, registry: DeterministicPriceRegistry) -> None:
        self._registry = registry

    def calculate(
        self,
        usage: ProviderUsageEvent,
        *,
        cost_record_id: str,
        pricing_date: date | None = None,
        recorded_at: datetime | None = None,
    ) -> ProviderCostCalculation:
        selected_date = pricing_date or usage.observed_at.date()
        price = self._registry.find(usage, pricing_date=selected_date)
        quantities = {item.unit: item.quantity for item in usage.quantities}
        rates = {item.usage_unit: item for item in price.rates}
        self._validate_rate_shape(rates)

        lines: list[CostCalculationLineItem] = []
        for unit in sorted(rates, key=lambda value: value.value):
            if unit not in quantities:
                raise CostCalculationError(
                    f"priced usage unit is absent from event: {unit.value}"
                )
            rate = rates[unit]
            observed = quantities[unit]
            billable = self._billable_quantity(unit, quantities, rates)
            lines.append(
                CostCalculationLineItem(
                    usage_unit=unit,
                    observed_quantity=observed,
                    billable_quantity=billable,
                    unit_size=rate.unit_size,
                    rate_amount=rate.rate_amount,
                    amount=billable / rate.unit_size * rate.rate_amount,
                    currency=rate.currency,
                )
            )

        amount = sum((item.amount for item in lines), start=Decimal(0))
        cost = CostRecord(
            cost_record_id=cost_record_id,
            execution_id=usage.execution_id,
            usage_event_id=usage.usage_event_id,
            cost_kind=CostKind.ESTIMATED,
            amount=amount,
            currency=price.rates[0].currency,
            price_entry_id=price.price_entry_id,
            registry_version=price.registry_version,
            source_reference=price.source_reference,
            recorded_at=recorded_at or usage.observed_at,
        )
        return ProviderCostCalculation(
            usage_event=usage,
            price_entry=price,
            line_items=tuple(lines),
            cost_record=cost,
        )

    @staticmethod
    def _validate_rate_shape(rates: dict[UsageUnit, object]) -> None:
        token_units = {
            UsageUnit.INPUT_TOKEN,
            UsageUnit.CACHED_INPUT_TOKEN,
            UsageUnit.OUTPUT_TOKEN,
            UsageUnit.REASONING_TOKEN,
        }
        if UsageUnit.TOTAL_TOKEN in rates and token_units.intersection(rates):
            raise CostCalculationError(
                "total-token rate cannot be combined with component token rates"
            )
        if UsageUnit.CACHED_INPUT_TOKEN in rates and UsageUnit.INPUT_TOKEN not in rates:
            raise CostCalculationError("cached-input rate requires an input-token rate")
        if UsageUnit.REASONING_TOKEN in rates and UsageUnit.OUTPUT_TOKEN not in rates:
            raise CostCalculationError(
                "reasoning-token rate requires an output-token rate"
            )

    @staticmethod
    def _billable_quantity(
        unit: UsageUnit,
        quantities: dict[UsageUnit, Decimal],
        rates: dict[UsageUnit, object],
    ) -> Decimal:
        observed = quantities[unit]
        if unit is UsageUnit.INPUT_TOKEN and UsageUnit.CACHED_INPUT_TOKEN in rates:
            return observed - quantities.get(UsageUnit.CACHED_INPUT_TOKEN, Decimal(0))
        if unit is UsageUnit.OUTPUT_TOKEN and UsageUnit.REASONING_TOKEN in rates:
            return observed - quantities.get(UsageUnit.REASONING_TOKEN, Decimal(0))
        return observed
