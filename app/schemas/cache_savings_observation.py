"""Strict contracts for observable cache work and estimated savings."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.persistent_cache_status import CacheKind
from app.schemas.provider_cost import CostKind, ProviderUsageEvent, UsageValueKind
from app.schemas.provider_cost_calculation import ProviderCostCalculation


class CacheWorkUnit(StrEnum):
    """The concrete unit whose repeated work a cache can avoid."""

    EMBEDDING_TEXT = "embedding_text"
    PARSED_DOCUMENT = "parsed_document"


class CacheAccessObservation(BaseModel):
    """Exact cumulative counters from one instrumented cache boundary."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    observation_id: str
    execution_id: str
    stage_name: str
    cache_kind: CacheKind
    cache_identity: str
    work_unit: CacheWorkUnit
    lookup_count: int = Field(ge=0)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    write_count: int = Field(ge=0)
    hit_input_bytes: int = Field(ge=0)
    miss_input_bytes: int = Field(ge=0)

    @field_validator("observation_id", "execution_id", "stage_name", "cache_identity")
    @classmethod
    def validate_normalized_text(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("cache observation identity fields must be normalized")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.lookup_count != self.hit_count + self.miss_count:
            raise ValueError("lookup count must equal cache hits plus misses")
        expected_unit = {
            CacheKind.EMBEDDING: CacheWorkUnit.EMBEDDING_TEXT,
            CacheKind.PARSED: CacheWorkUnit.PARSED_DOCUMENT,
        }[self.cache_kind]
        if self.work_unit is not expected_unit:
            raise ValueError("work unit must match cache kind")
        return self

    @property
    def avoided_work_unit_count(self) -> int:
        """Return directly observed reusable work items, without call inflation."""

        return self.hit_count


class CacheSavingsReport(BaseModel):
    """Exact cache counters plus an optional, explicitly estimated saving."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    observation: CacheAccessObservation
    counterfactual_usage: ProviderUsageEvent | None = None
    estimated_avoided_cost: ProviderCostCalculation | None = None
    provider_calls_avoided: int | None = Field(default=None, ge=0)
    exact_provider_token_savings_validated: bool = False
    exact_billed_cost_savings_validated: bool = False
    limitations: tuple[str, ...] = Field(min_length=1, max_length=16)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("cache savings limitations must be normalized")
        if len(values) != len(set(values)):
            raise ValueError("cache savings limitations must be unique")
        return values

    @model_validator(mode="after")
    def validate_savings_boundary(self) -> Self:
        paired = (self.counterfactual_usage is None) == (
            self.estimated_avoided_cost is None
        )
        if not paired:
            raise ValueError(
                "counterfactual usage and estimated avoided cost must appear together"
            )
        if self.counterfactual_usage is not None:
            usage = self.counterfactual_usage
            calculation = self.estimated_avoided_cost
            assert calculation is not None
            if usage.value_kind is not UsageValueKind.PLANNED:
                raise ValueError(
                    "avoided usage must be an explicit planned counterfactual"
                )
            if usage.execution_id != self.observation.execution_id:
                raise ValueError(
                    "counterfactual and observation execution IDs must match"
                )
            if calculation.usage_event != usage:
                raise ValueError(
                    "cost calculation must use the exact counterfactual event"
                )
            if calculation.cost_record.cost_kind is not CostKind.ESTIMATED:
                raise ValueError("avoided monetary cost must remain estimated")
        if self.exact_provider_token_savings_validated:
            raise ValueError(
                "runtime cache counters do not prove exact provider tokens"
            )
        if self.exact_billed_cost_savings_validated:
            raise ValueError("runtime cache counters do not prove billed cost savings")
        return self
