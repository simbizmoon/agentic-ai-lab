"""Component-specific runtime lock for the Stage 9 single-agent baseline."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.monetary_cost_budget import MonetaryCostBudget
from app.schemas.provider_cost import ModelPriceEntry
from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9BaselineExperimentPlan,
)


class Stage9RuntimeComponentRole(StrEnum):
    PLANNER = "planner"
    GROUNDED_ANSWER_GENERATOR = "grounded_answer_generator"
    CITATION_EVALUATOR = "citation_evaluator"


class Stage9RuntimeComponentLock(BaseModel):
    """One exact provider/model/operation choice and its applicable price."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    role: Stage9RuntimeComponentRole
    provider_name: str
    model_name: str
    operation: str
    reasoning_effort: str | None = None
    pricing_date: date
    price_entry: ModelPriceEntry

    @model_validator(mode="after")
    def validate_component(self) -> Self:
        for value in (self.provider_name, self.model_name, self.operation):
            if not value.strip() or value != value.strip():
                raise ValueError("runtime component identity must be normalized")
        if self.reasoning_effort is not None and (
            not self.reasoning_effort.strip()
            or self.reasoning_effort != self.reasoning_effort.strip()
        ):
            raise ValueError("reasoning effort must be normalized when supplied")
        price = self.price_entry
        if price.model_name is None:
            raise ValueError("component price must identify an exact model")
        if (
            price.provider_name.casefold() != self.provider_name.casefold()
            or price.model_name.casefold() != self.model_name.casefold()
            or price.operation.casefold() != self.operation.casefold()
        ):
            raise ValueError("component and price identity must match exactly")
        if not (
            price.effective_from <= self.pricing_date
            and (
                price.effective_through is None
                or self.pricing_date <= price.effective_through
            )
        ):
            raise ValueError("component price is not effective on pricing date")
        return self


class Stage9BaselineRuntimeStack(BaseModel):
    """All model-bearing components needed for an auditable baseline."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    stack_id: str
    stack_version: str
    components: tuple[Stage9RuntimeComponentLock, ...] = Field(
        min_length=3, max_length=3
    )

    @model_validator(mode="after")
    def validate_stack(self) -> Self:
        for value in (self.stack_id, self.stack_version):
            if not value.strip() or value != value.strip():
                raise ValueError("runtime stack identity must be normalized")
        roles = [component.role for component in self.components]
        if len(roles) != len(set(roles)) or set(roles) != set(
            Stage9RuntimeComponentRole
        ):
            raise ValueError(
                "runtime stack must contain each required role exactly once"
            )
        registry_versions = {
            component.price_entry.registry_version for component in self.components
        }
        if len(registry_versions) != 1:
            raise ValueError("runtime stack must use one price registry version")
        pricing_dates = {component.pricing_date for component in self.components}
        if len(pricing_dates) != 1:
            raise ValueError("runtime stack must use one locked pricing date")
        return self

    def component(self, role: Stage9RuntimeComponentRole) -> Stage9RuntimeComponentLock:
        return next(item for item in self.components if item.role is role)


class Stage9LockedBaselineExperiment(BaseModel):
    """Baseline plan bound to every model-bearing runtime component."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    plan: Stage9BaselineExperimentPlan
    runtime_stack: Stage9BaselineRuntimeStack

    @model_validator(mode="after")
    def validate_experiment(self) -> Self:
        generator = self.runtime_stack.component(
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR
        )
        manifest = self.plan.manifest
        if (
            manifest.provider_name.casefold() != generator.provider_name.casefold()
            or manifest.model_name.casefold() != generator.model_name.casefold()
        ):
            raise ValueError(
                "manifest model must identify the grounded-answer generator"
            )
        registry_version = generator.price_entry.registry_version
        if manifest.price_registry_version != registry_version:
            raise ValueError("manifest and runtime price registry versions must match")
        budget: MonetaryCostBudget = manifest.execution_budget
        currencies = {
            rate.currency
            for component in self.runtime_stack.components
            for rate in component.price_entry.rates
        }
        if currencies != {budget.currency}:
            raise ValueError(
                "all runtime prices must match the monetary budget currency"
            )
        return self
