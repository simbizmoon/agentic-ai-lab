"""Append-only execution usage and cost ledger contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.provider_cost import CostKind, CostRecord, ProviderUsageEvent


class UsageCostLedgerEntry(BaseModel):
    """One usage event with an explicit monetary state."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    usage_event: ProviderUsageEvent
    cost_record: CostRecord

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        if self.cost_record.execution_id != self.usage_event.execution_id:
            raise ValueError("ledger entry execution IDs must match")
        if self.cost_record.usage_event_id != self.usage_event.usage_event_id:
            raise ValueError("cost must reference the exact ledger usage event")
        return self


class CostLedgerTotal(BaseModel):
    """One exact total separated by cost authority and currency."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cost_kind: CostKind
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(ge=Decimal(0))

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if self.cost_kind in {CostKind.NOT_APPLICABLE, CostKind.UNAVAILABLE}:
            raise ValueError("non-monetary cost kinds must not have ledger totals")
        if not self.amount.is_finite():
            raise ValueError("ledger total amount must be finite")
        return self


class ExecutionUsageCostLedger(BaseModel):
    """Immutable snapshot of one execution's append-only accounting entries."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ledger_id: str
    execution_id: str
    entries: tuple[UsageCostLedgerEntry, ...] = Field(default=(), max_length=10_000)
    totals: tuple[CostLedgerTotal, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_ledger(self) -> Self:
        for field_name in ("ledger_id", "execution_id"):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        if any(
            item.usage_event.execution_id != self.execution_id for item in self.entries
        ):
            raise ValueError("all ledger entries must belong to the execution")
        usage_ids = [item.usage_event.usage_event_id for item in self.entries]
        cost_ids = [item.cost_record.cost_record_id for item in self.entries]
        if len(usage_ids) != len(set(usage_ids)):
            raise ValueError("ledger usage event IDs must be unique")
        if len(cost_ids) != len(set(cost_ids)):
            raise ValueError("ledger cost record IDs must be unique")

        expected: dict[tuple[CostKind, str], Decimal] = {}
        for item in self.entries:
            cost = item.cost_record
            if cost.amount is None or cost.currency is None:
                continue
            key = (cost.cost_kind, cost.currency)
            expected[key] = expected.get(key, Decimal(0)) + cost.amount
        expected_totals = tuple(
            CostLedgerTotal(cost_kind=kind, currency=currency, amount=amount)
            for (kind, currency), amount in sorted(
                expected.items(), key=lambda item: (item[0][0].value, item[0][1])
            )
        )
        if self.totals != expected_totals:
            raise ValueError("ledger totals must exactly match monetary entries")
        return self
