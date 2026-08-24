"""Typed results for deterministic provider cost calculation."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.provider_cost import (
    CostRecord,
    ModelPriceEntry,
    ProviderUsageEvent,
    UsageUnit,
)


class CostCalculationLineItem(BaseModel):
    """One exact rate application without hidden rounding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    usage_unit: UsageUnit
    observed_quantity: Decimal = Field(ge=Decimal(0))
    billable_quantity: Decimal = Field(ge=Decimal(0))
    unit_size: Decimal = Field(gt=Decimal(0))
    rate_amount: Decimal = Field(ge=Decimal(0))
    amount: Decimal = Field(ge=Decimal(0))
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_line_item(self) -> Self:
        values = (
            self.observed_quantity,
            self.billable_quantity,
            self.unit_size,
            self.rate_amount,
            self.amount,
        )
        if any(not value.is_finite() for value in values):
            raise ValueError("cost calculation decimals must be finite")
        expected = self.billable_quantity / self.unit_size * self.rate_amount
        if self.amount != expected:
            raise ValueError("line-item amount must equal exact rate calculation")
        if self.billable_quantity > self.observed_quantity:
            raise ValueError("billable quantity must not exceed observed quantity")
        return self


class ProviderCostCalculation(BaseModel):
    """One usage event bound to an effective price and exact cost lines."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    usage_event: ProviderUsageEvent
    price_entry: ModelPriceEntry
    line_items: tuple[CostCalculationLineItem, ...] = Field(min_length=1, max_length=32)
    cost_record: CostRecord

    @model_validator(mode="after")
    def validate_calculation(self) -> Self:
        if self.cost_record.usage_event_id != self.usage_event.usage_event_id:
            raise ValueError("cost record must reference the exact usage event")
        if self.cost_record.execution_id != self.usage_event.execution_id:
            raise ValueError("cost and usage execution IDs must match")
        if self.cost_record.price_entry_id != self.price_entry.price_entry_id:
            raise ValueError("cost record must reference the exact price entry")
        if self.cost_record.registry_version != self.price_entry.registry_version:
            raise ValueError("cost and price registry versions must match")
        currencies = {item.currency for item in self.line_items}
        if currencies != {self.cost_record.currency}:
            raise ValueError("line-item and total currencies must match")
        if self.cost_record.amount != sum(
            (item.amount for item in self.line_items), start=Decimal(0)
        ):
            raise ValueError("cost record amount must equal exact line-item sum")
        units = [item.usage_unit for item in self.line_items]
        if units != sorted(units, key=lambda value: value.value):
            raise ValueError("cost line items must use canonical unit order")
        if len(units) != len(set(units)):
            raise ValueError("cost line-item units must be unique")
        return self
