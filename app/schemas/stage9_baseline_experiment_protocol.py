"""Locked execution protocol for the Stage 9 single-agent baseline."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.stage9_evaluation_manifest import (
    Stage9DatasetPartition,
    Stage9ExperimentManifest,
)


class Stage9ExecutionPhase(StrEnum):
    DEVELOPMENT = "development"
    BLIND_HOLDOUT = "blind_holdout"


class Stage9OperationalBudget(BaseModel):
    """Non-monetary hard ceilings for one complete baseline execution."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_provider_requests: int = Field(ge=1, le=100_000)
    maximum_external_requests: int = Field(ge=1, le=100_000)
    maximum_recorded_tokens: int = Field(ge=1, le=100_000_000)
    maximum_elapsed_seconds: float = Field(gt=0, le=604_800)

    @model_validator(mode="after")
    def validate_request_bounds(self) -> Self:
        if self.maximum_external_requests < self.maximum_provider_requests:
            raise ValueError(
                "external-request ceiling must cover every provider request"
            )
        return self


class Stage9ExecutionProtocol(BaseModel):
    """Frozen order and anti-tuning rules for development and blind holdout."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    protocol_id: str
    protocol_version: str
    phase_order: tuple[Stage9ExecutionPhase, ...] = (
        Stage9ExecutionPhase.DEVELOPMENT,
        Stage9ExecutionPhase.BLIND_HOLDOUT,
    )
    allow_development_adjustment: bool = True
    require_new_manifest_after_development_adjustment: bool = True
    allow_holdout_adjustment: bool = False
    reveal_holdout_before_manifest_lock: bool = False
    preserve_failed_runs: bool = True

    @model_validator(mode="after")
    def validate_protocol(self) -> Self:
        for value in (self.protocol_id, self.protocol_version):
            if not value.strip() or value != value.strip():
                raise ValueError("protocol identity must be normalized and nonblank")
        if self.phase_order != (
            Stage9ExecutionPhase.DEVELOPMENT,
            Stage9ExecutionPhase.BLIND_HOLDOUT,
        ):
            raise ValueError("development must run before blind holdout")
        if self.allow_development_adjustment and not (
            self.require_new_manifest_after_development_adjustment
        ):
            raise ValueError("development adjustment requires a new locked manifest")
        if self.allow_holdout_adjustment or self.reveal_holdout_before_manifest_lock:
            raise ValueError("blind holdout must not tune or precede manifest lock")
        if not self.preserve_failed_runs:
            raise ValueError("failed baseline runs must remain auditable")
        return self


class Stage9BaselineExperimentPlan(BaseModel):
    """One immutable manifest plus the budgets and protocol needed to run it."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    manifest: Stage9ExperimentManifest
    operational_budget: Stage9OperationalBudget
    protocol: Stage9ExecutionProtocol
    development_case_ids: tuple[str, ...] = Field(min_length=1)
    blind_holdout_case_ids: tuple[str, ...] = Field(min_length=1)
    planned_case_executions: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        development = tuple(
            case.definition.case_id
            for case in self.manifest.cases
            if case.partition is Stage9DatasetPartition.DEVELOPMENT
        )
        holdout = tuple(
            case.definition.case_id
            for case in self.manifest.cases
            if case.partition is Stage9DatasetPartition.LOCKED
        )
        if self.development_case_ids != development:
            raise ValueError("development IDs must match the locked manifest order")
        if self.blind_holdout_case_ids != holdout:
            raise ValueError("holdout IDs must match the locked manifest order")
        expected_executions = len(self.manifest.cases) * (
            self.manifest.repetitions_per_case
        )
        if self.planned_case_executions != expected_executions:
            raise ValueError("planned executions must equal cases times repetitions")
        minimum_requests = self.planned_case_executions
        if self.operational_budget.maximum_provider_requests < minimum_requests:
            raise ValueError(
                "provider-request ceiling cannot cover one request per planned run"
            )
        return self
