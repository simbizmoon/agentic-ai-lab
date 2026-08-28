"""Provider-neutral usage, price, and cost accounting contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UsageUnit(StrEnum):
    """A measurable provider resource without assigning a monetary value."""

    REQUEST = "request"
    PROVIDER_CALL = "provider_call"
    TOOL_CALL = "tool_call"
    EXTERNAL_REQUEST = "external_request"
    AGENT_ROUND = "agent_round"
    RECORDED_TOKEN = "recorded_token"
    INPUT_TOKEN = "input_token"
    CACHED_INPUT_TOKEN = "cached_input_token"
    OUTPUT_TOKEN = "output_token"
    REASONING_TOKEN = "reasoning_token"
    TOTAL_TOKEN = "total_token"
    EMBEDDING_TOKEN = "embedding_token"
    SEARCH_CREDIT = "search_credit"
    LOCAL_COMPUTE_SECOND = "local_compute_second"


class UsageValueKind(StrEnum):
    """How a usage quantity was obtained."""

    PLANNED = "planned"
    OBSERVED = "observed"
    PROVIDER_REPORTED = "provider_reported"


class CostKind(StrEnum):
    """The authority and meaning of one monetary cost value."""

    ESTIMATED = "estimated"
    PROVIDER_REPORTED = "provider_reported"
    BILLED = "billed"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


_INTEGRAL_USAGE_UNITS = {
    UsageUnit.REQUEST,
    UsageUnit.PROVIDER_CALL,
    UsageUnit.TOOL_CALL,
    UsageUnit.EXTERNAL_REQUEST,
    UsageUnit.AGENT_ROUND,
    UsageUnit.RECORDED_TOKEN,
    UsageUnit.INPUT_TOKEN,
    UsageUnit.CACHED_INPUT_TOKEN,
    UsageUnit.OUTPUT_TOKEN,
    UsageUnit.REASONING_TOKEN,
    UsageUnit.TOTAL_TOKEN,
    UsageUnit.EMBEDDING_TOKEN,
}


class UsageQuantity(BaseModel):
    """One non-negative resource quantity in an explicit unit."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    unit: UsageUnit
    quantity: Decimal = Field(ge=Decimal(0))

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal, info: object) -> Decimal:
        if not value.is_finite():
            raise ValueError("usage quantity must be finite")
        unit = getattr(info, "data", {}).get("unit")
        if unit in _INTEGRAL_USAGE_UNITS and value != value.to_integral_value():
            raise ValueError(f"{unit.value} quantity must be an integer")
        return value


class ProviderUsageEvent(BaseModel):
    """One append-only, provider-neutral usage observation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    usage_event_id: str
    execution_id: str
    stage_name: str
    provider_name: str
    model_name: str | None = None
    operation: str
    request_id: str | None = None
    response_id: str | None = None
    observed_at: datetime
    value_kind: UsageValueKind
    quantities: tuple[UsageQuantity, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        for field_name in (
            "usage_event_id",
            "execution_id",
            "stage_name",
            "provider_name",
            "operation",
        ):
            self._require_normalized(field_name, getattr(self, field_name))
        for field_name in ("model_name", "request_id", "response_id"):
            value = getattr(self, field_name)
            if value is not None:
                self._require_normalized(field_name, value)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        units = [item.unit for item in self.quantities]
        if len(units) != len(set(units)):
            raise ValueError("usage quantity units must be unique within an event")
        by_unit = {item.unit: item.quantity for item in self.quantities}
        self._validate_token_usage(by_unit)
        return self

    @staticmethod
    def _require_normalized(field_name: str, value: str) -> None:
        if not value.strip() or value != value.strip():
            raise ValueError(f"{field_name} must be normalized and nonblank")

    @staticmethod
    def _validate_token_usage(by_unit: dict[UsageUnit, Decimal]) -> None:
        core = {
            UsageUnit.INPUT_TOKEN,
            UsageUnit.OUTPUT_TOKEN,
            UsageUnit.TOTAL_TOKEN,
        }
        supplied = core.intersection(by_unit)
        if supplied and supplied != core:
            raise ValueError(
                "input, output, and total token quantities must be supplied together"
            )
        if supplied and (
            by_unit[UsageUnit.TOTAL_TOKEN]
            != by_unit[UsageUnit.INPUT_TOKEN] + by_unit[UsageUnit.OUTPUT_TOKEN]
        ):
            raise ValueError("total tokens must equal input plus output tokens")
        cached = by_unit.get(UsageUnit.CACHED_INPUT_TOKEN)
        if cached is not None:
            input_tokens = by_unit.get(UsageUnit.INPUT_TOKEN)
            if input_tokens is None or cached > input_tokens:
                raise ValueError(
                    "cached input tokens require and must not exceed input"
                )
        reasoning = by_unit.get(UsageUnit.REASONING_TOKEN)
        if reasoning is not None:
            output_tokens = by_unit.get(UsageUnit.OUTPUT_TOKEN)
            if output_tokens is None or reasoning > output_tokens:
                raise ValueError("reasoning tokens require and must not exceed output")


class PriceRate(BaseModel):
    """A deterministic monetary rate for one explicit usage unit."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    usage_unit: UsageUnit
    unit_size: Decimal = Field(gt=Decimal(0))
    rate_amount: Decimal = Field(ge=Decimal(0))
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("unit_size", "rate_amount")
    @classmethod
    def validate_finite_decimal(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("price values must be finite")
        return value

    @model_validator(mode="after")
    def validate_integral_unit_size(self) -> Self:
        if (
            self.usage_unit in _INTEGRAL_USAGE_UNITS
            and self.unit_size != self.unit_size.to_integral_value()
        ):
            raise ValueError("integral usage units require an integer unit_size")
        return self


class ModelPriceEntry(BaseModel):
    """Versioned and effective-dated rates for one provider operation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    price_entry_id: str
    registry_version: str
    provider_name: str
    model_name: str | None = None
    operation: str
    effective_from: date
    effective_through: date | None = None
    source_reference: str
    rates: tuple[PriceRate, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        for field_name in (
            "price_entry_id",
            "registry_version",
            "provider_name",
            "operation",
            "source_reference",
        ):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        if self.model_name is not None and (
            not self.model_name.strip() or self.model_name != self.model_name.strip()
        ):
            raise ValueError("model_name must be normalized when supplied")
        if (
            self.effective_through is not None
            and self.effective_through < self.effective_from
        ):
            raise ValueError("effective_through must not precede effective_from")
        units = [rate.usage_unit for rate in self.rates]
        if len(units) != len(set(units)):
            raise ValueError("price rates must have unique usage units")
        currencies = {rate.currency for rate in self.rates}
        if len(currencies) != 1:
            raise ValueError("one price entry must use exactly one currency")
        return self


class CostRecord(BaseModel):
    """A monetary result whose authority is explicit and auditable."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cost_record_id: str
    execution_id: str
    usage_event_id: str | None = None
    cost_kind: CostKind
    amount: Decimal | None = Field(default=None, ge=Decimal(0))
    currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    price_entry_id: str | None = None
    registry_version: str | None = None
    source_reference: str | None = None
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        for field_name in ("cost_record_id", "execution_id"):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        for field_name in (
            "usage_event_id",
            "price_entry_id",
            "registry_version",
            "source_reference",
        ):
            value = getattr(self, field_name)
            if value is not None and (not value.strip() or value != value.strip()):
                raise ValueError(f"{field_name} must be normalized when supplied")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.amount is not None and not self.amount.is_finite():
            raise ValueError("cost amount must be finite")

        monetary = {
            CostKind.ESTIMATED,
            CostKind.PROVIDER_REPORTED,
            CostKind.BILLED,
        }
        if self.cost_kind in monetary:
            if self.amount is None or self.currency is None:
                raise ValueError("monetary cost requires amount and currency")
        elif self.amount is not None or self.currency is not None:
            raise ValueError(
                "not_applicable and unavailable cost must not invent money values"
            )

        if self.cost_kind is CostKind.ESTIMATED:
            if (
                self.usage_event_id is None
                or self.price_entry_id is None
                or self.registry_version is None
                or self.source_reference is None
            ):
                raise ValueError(
                    "estimated cost requires usage and complete price provenance"
                )
        elif self.cost_kind in {CostKind.PROVIDER_REPORTED, CostKind.BILLED}:
            if self.source_reference is None:
                raise ValueError("reported or billed cost requires source_reference")
        elif any(
            value is not None for value in (self.price_entry_id, self.registry_version)
        ):
            raise ValueError(
                "non-monetary cost must not contain price registry provenance"
            )
        return self
