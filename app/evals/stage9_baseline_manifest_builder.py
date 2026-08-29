"""Build a Stage 9 baseline plan only from exact locked inputs."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.evals.stage9_locked_dataset_importer import (
    EXPECTED_CASE_IDS,
    _build_case,
    _verify_input,
)
from app.schemas.monetary_cost_budget import CostBudgetBasis, MonetaryCostBudget
from app.schemas.provider_cost import ModelPriceEntry
from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9BaselineExperimentPlan,
    Stage9ExecutionProtocol,
    Stage9OperationalBudget,
)
from app.schemas.stage9_evaluation_manifest import (
    Stage9DatasetPartition,
    Stage9ExperimentManifest,
    Stage9HumanReviewRubric,
)

CANONICAL_DATASET_SHA256 = (
    "9405c96ec598c89ba2d7097dea61d01a9485c7f71a5bb4ac872da728999d0b2a"
)


class Stage9BaselineManifestSettings(BaseModel):
    """Explicit runtime choices; no provider, model, or price default is inferred."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    manifest_id: str
    manifest_version: str
    system_profile_id: str
    price_entry: ModelPriceEntry
    pricing_date: date
    repetitions_per_case: int
    monetary_budget: MonetaryCostBudget
    operational_budget: Stage9OperationalBudget
    protocol: Stage9ExecutionProtocol
    human_review_rubric: Stage9HumanReviewRubric

    @field_validator("manifest_id", "manifest_version", "system_profile_id")
    @classmethod
    def normalized_identity(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("baseline identity must be normalized and nonblank")
        return value

    @field_validator("repetitions_per_case")
    @classmethod
    def bounded_repetitions(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("repetitions must be between one and five")
        return value

    @model_validator(mode="after")
    def validate_price_and_budget_authority(self) -> Self:
        price = self.price_entry
        if price.model_name is None:
            raise ValueError("baseline price must identify an exact model")
        if not (
            price.effective_from <= self.pricing_date
            and (
                price.effective_through is None
                or self.pricing_date <= price.effective_through
            )
        ):
            raise ValueError("price entry is not effective on the locked pricing date")
        currencies = {rate.currency for rate in price.rates}
        if currencies != {self.monetary_budget.currency}:
            raise ValueError("price and monetary budget currencies must match")
        if self.monetary_budget.basis is not CostBudgetBasis.ESTIMATED:
            raise ValueError(
                "registry-priced baseline requires an estimated-cost budget"
            )
        return self


class Stage9BaselineManifestBuilder:
    """Pure builder that verifies the canonical Dataset before creating a plan."""

    def build(
        self,
        *,
        dataset_path: Path,
        settings: Stage9BaselineManifestSettings,
    ) -> Stage9BaselineExperimentPlan:
        locked = _verify_input(dataset_path)
        if locked["dataset_sha256"] != CANONICAL_DATASET_SHA256:
            raise ValueError("Stage 9 canonical semantic checksum mismatch")
        if tuple(locked["case_order"]) != EXPECTED_CASE_IDS:
            raise ValueError("Stage 9 canonical case order mismatch")

        cases = tuple(_build_case(item) for item in locked["cases"])
        development = tuple(
            case.definition.case_id
            for case in cases
            if case.partition is Stage9DatasetPartition.DEVELOPMENT
        )
        holdout = tuple(
            case.definition.case_id
            for case in cases
            if case.partition is Stage9DatasetPartition.LOCKED
        )
        planned = len(cases) * settings.repetitions_per_case
        manifest = Stage9ExperimentManifest(
            manifest_id=settings.manifest_id,
            manifest_version=settings.manifest_version,
            dataset_id=locked["dataset_id"],
            dataset_version=locked["dataset_version"],
            dataset_sha256=locked["dataset_sha256"],
            system_profile_id=settings.system_profile_id,
            architecture="bounded_single_agent",
            provider_name=settings.price_entry.provider_name,
            model_name=settings.price_entry.model_name,
            price_registry_version=settings.price_entry.registry_version,
            cases=cases,
            case_order=EXPECTED_CASE_IDS,
            repetitions_per_case=settings.repetitions_per_case,
            execution_budget=settings.monetary_budget,
            human_review_rubric=settings.human_review_rubric,
        )
        return Stage9BaselineExperimentPlan(
            manifest=manifest,
            operational_budget=settings.operational_budget,
            protocol=settings.protocol,
            development_case_ids=development,
            blind_holdout_case_ids=holdout,
            planned_case_executions=planned,
        )
