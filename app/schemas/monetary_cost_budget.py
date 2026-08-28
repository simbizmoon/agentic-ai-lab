"""Contracts for deterministic monetary execution-budget decisions."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.provider_cost import CostKind, CostRecord
from app.schemas.provider_cost_ledger import ExecutionUsageCostLedger


class CostBudgetBasis(StrEnum):
    """The one cost authority used for a budget decision."""

    ESTIMATED = "estimated"
    PROVIDER_REPORTED = "provider_reported"
    BILLED = "billed"

    @property
    def cost_kind(self) -> CostKind:
        return CostKind(self.value)


class CostBudgetDecision(StrEnum):
    """Explicit next action; no decision silently raises the ceiling."""

    CONTINUE = "continue"
    SCOPE_REDUCTION_REQUIRED = "scope_reduction_required"
    LOWER_COST_PATH_REQUIRED = "lower_cost_path_required"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    STOP = "stop"


class CostBudgetReason(StrEnum):
    """Stable reason codes for audit and tests."""

    WITHIN_BUDGET = "within_budget"
    COST_UNAVAILABLE_ALLOWED = "cost_unavailable_allowed"
    COST_UNAVAILABLE = "cost_unavailable"
    PROJECTED_COST_EXCEEDS_LIMIT = "projected_cost_exceeds_limit"


class MonetaryCostBudget(BaseModel):
    """One explicit currency ceiling for one cost authority."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    basis: CostBudgetBasis = CostBudgetBasis.ESTIMATED
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    maximum_execution_cost: Decimal = Field(ge=Decimal(0))
    require_complete_cost: bool = True

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if not self.maximum_execution_cost.is_finite():
            raise ValueError("maximum_execution_cost must be finite")
        return self


class MonetaryCostBudgetRequest(BaseModel):
    """Ledger, optional next cost, and explicitly available remedies."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ledger: ExecutionUsageCostLedger
    budget: MonetaryCostBudget
    proposed_cost: CostRecord | None = None
    scope_reduction_available: bool = False
    lower_cost_path_available: bool = False
    human_approval_allowed: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        proposed = self.proposed_cost
        if proposed is not None:
            if proposed.execution_id != self.ledger.execution_id:
                raise ValueError("proposed cost must belong to the ledger execution")
            if proposed.cost_kind not in {
                self.budget.basis.cost_kind,
                CostKind.UNAVAILABLE,
                CostKind.NOT_APPLICABLE,
            }:
                raise ValueError("proposed cost kind must match the budget basis")
            if (
                proposed.amount is not None
                and proposed.currency != self.budget.currency
            ):
                raise ValueError("proposed cost currency must match the budget")
        return self


class MonetaryCostBudgetResult(BaseModel):
    """Auditable budget arithmetic and the required next action."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    execution_id: str
    basis: CostBudgetBasis
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    maximum_execution_cost: Decimal = Field(ge=Decimal(0))
    accumulated_cost: Decimal = Field(ge=Decimal(0))
    proposed_increment: Decimal = Field(ge=Decimal(0))
    projected_cost: Decimal = Field(ge=Decimal(0))
    remaining_cost: Decimal = Field(ge=Decimal(0))
    overage_cost: Decimal = Field(ge=Decimal(0))
    unavailable_cost_count: int = Field(ge=0)
    cost_complete: bool
    checked_cost_record_ids: tuple[str, ...] = Field(default=(), max_length=10_001)
    decision: CostBudgetDecision
    reason: CostBudgetReason
    budget_exceeded: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        decimals = (
            self.maximum_execution_cost,
            self.accumulated_cost,
            self.proposed_increment,
            self.projected_cost,
            self.remaining_cost,
            self.overage_cost,
        )
        if any(not value.is_finite() for value in decimals):
            raise ValueError("budget result decimals must be finite")
        if self.projected_cost != self.accumulated_cost + self.proposed_increment:
            raise ValueError("projected cost must equal accumulated plus proposed")
        expected_remaining = max(
            self.maximum_execution_cost - self.projected_cost, Decimal(0)
        )
        expected_overage = max(
            self.projected_cost - self.maximum_execution_cost, Decimal(0)
        )
        if self.remaining_cost != expected_remaining:
            raise ValueError("remaining cost arithmetic is inconsistent")
        if self.overage_cost != expected_overage:
            raise ValueError("overage cost arithmetic is inconsistent")
        if self.budget_exceeded != (self.overage_cost > 0):
            raise ValueError("budget_exceeded must match positive overage")
        if len(self.checked_cost_record_ids) != len(set(self.checked_cost_record_ids)):
            raise ValueError("checked cost record IDs must be unique")
        if self.cost_complete != (self.unavailable_cost_count == 0):
            raise ValueError("cost_complete must match unavailable cost count")
        if self.reason is CostBudgetReason.WITHIN_BUDGET:
            if self.decision is not CostBudgetDecision.CONTINUE:
                raise ValueError("within-budget result must continue")
            if self.budget_exceeded or self.unavailable_cost_count:
                raise ValueError("within-budget result must be complete and bounded")
        elif self.reason is CostBudgetReason.COST_UNAVAILABLE_ALLOWED:
            if self.decision is not CostBudgetDecision.CONTINUE:
                raise ValueError("allowed unavailable cost must continue")
            if self.cost_complete or self.budget_exceeded:
                raise ValueError(
                    "allowed unavailable cost must be incomplete and within budget"
                )
        elif self.decision is CostBudgetDecision.CONTINUE:
            raise ValueError("non-passing budget reason must not continue")
        return self
