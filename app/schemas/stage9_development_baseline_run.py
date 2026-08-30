"""Contracts for the bounded Stage 9 development-only baseline run."""

from __future__ import annotations

import math
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.provider_cost import CostKind

STAGE9_DEVELOPMENT_CASE_IDS = (
    "tech-01",
    "academic-01",
    "patent-01",
    "cross-01",
)
STAGE9_BLIND_HOLDOUT_CASE_IDS = frozenset(
    {
        "tech-02",
        "academic-02",
        "patent-02",
        "patent-03",
        "cross-02",
        "cross-03",
    }
)


class Stage9DevelopmentRunStatus(StrEnum):
    READY = "ready"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    STOPPED = "stopped"
    FAILED = "failed"


class Stage9DevelopmentCaseStatus(StrEnum):
    ANSWER_AVAILABLE = "answer_available"
    ABSTAINED = "abstained"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class Stage9HumanReviewStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class Stage9DevelopmentRunBudget(BaseModel):
    """Hard phase ceilings approved before development execution."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_provider_requests: int = Field(ge=1, le=16)
    maximum_external_requests: int = Field(ge=1, le=24)
    maximum_recorded_tokens: int = Field(ge=1, le=120_000)
    maximum_elapsed_seconds: float = Field(gt=0, le=2_880)
    maximum_estimated_cost: Decimal = Field(ge=Decimal(0), le=Decimal("1.50"))
    currency: str = Field(pattern=r"^USD$")

    @field_validator("maximum_elapsed_seconds", mode="before")
    @classmethod
    def finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("maximum elapsed seconds must be finite")
        return value

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if self.maximum_external_requests < self.maximum_provider_requests:
            raise ValueError("external ceiling must cover provider requests")
        if not self.maximum_estimated_cost.is_finite():
            raise ValueError("maximum estimated cost must be finite")
        return self


class Stage9DevelopmentRunRequest(BaseModel):
    """One exact development request that cannot name holdout cases."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    run_id: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    repetitions_per_case: int = Field(ge=1, le=1)
    budget: Stage9DevelopmentRunBudget
    allow_blind_holdout: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.run_id.strip() or self.run_id != self.run_id.strip():
            raise ValueError("run ID must be normalized and nonblank")
        if self.case_ids != STAGE9_DEVELOPMENT_CASE_IDS:
            raise ValueError("case IDs must exactly match the locked development order")
        if STAGE9_BLIND_HOLDOUT_CASE_IDS.intersection(self.case_ids):
            raise ValueError("development request must not reveal blind holdout cases")
        if self.allow_blind_holdout:
            raise ValueError("blind holdout execution is forbidden in development")
        return self


class Stage9DevelopmentCaseUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider_requests: int = Field(ge=0)
    external_requests: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    estimated_cost: Decimal = Field(ge=Decimal(0))
    currency: str = Field(pattern=r"^USD$")
    cost_kind: CostKind

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("case elapsed seconds must be finite")
        return value

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        if not self.estimated_cost.is_finite():
            raise ValueError("case estimated cost must be finite")
        if self.cost_kind is not CostKind.ESTIMATED:
            raise ValueError("development ledger uses estimated cost authority")
        if self.external_requests < self.provider_requests:
            raise ValueError("external requests must cover provider requests")
        return self


class Stage9DevelopmentCaseRecord(BaseModel):
    """Immutable reference to one case's separately persisted workflow artifact."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    case_id: str
    execution_id: str
    status: Stage9DevelopmentCaseStatus
    workflow_artifact_path: str
    workflow_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_model_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    usage: Stage9DevelopmentCaseUsage
    human_review_status: Stage9HumanReviewStatus = Stage9HumanReviewStatus.PENDING

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        for field_name in ("case_id", "execution_id", "workflow_artifact_path"):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        if self.case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            raise ValueError("case record must belong to the development partition")
        if self.case_id in STAGE9_BLIND_HOLDOUT_CASE_IDS:
            raise ValueError("blind holdout result cannot enter a development run")
        if any(
            not value.strip() or value != value.strip()
            for value in self.response_model_ids
        ):
            raise ValueError("response model IDs must be normalized and nonblank")
        return self


class Stage9DevelopmentRunUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider_requests: int = Field(ge=0)
    external_requests: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    estimated_cost: Decimal = Field(ge=Decimal(0))
    currency: str = Field(pattern=r"^USD$")
    cost_kind: CostKind

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("run elapsed seconds must be finite")
        return value

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        if not self.estimated_cost.is_finite():
            raise ValueError("run estimated cost must be finite")
        if self.cost_kind is not CostKind.ESTIMATED:
            raise ValueError("run ledger uses estimated cost authority")
        if self.external_requests < self.provider_requests:
            raise ValueError("external requests must cover provider requests")
        return self


class Stage9DevelopmentRunResult(BaseModel):
    """Development-only aggregate with exact arithmetic and ceiling checks."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: Stage9DevelopmentRunRequest
    status: Stage9DevelopmentRunStatus
    case_records: tuple[Stage9DevelopmentCaseRecord, ...] = Field(max_length=4)
    usage: Stage9DevelopmentRunUsage
    budget_exhausted: bool
    stop_reason: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        ids = tuple(record.case_id for record in self.case_records)
        expected_prefix = self.request.case_ids[: len(ids)]
        if ids != expected_prefix or len(ids) != len(set(ids)):
            raise ValueError("case records must be a unique development-order prefix")

        expected = Stage9DevelopmentRunUsage(
            provider_requests=sum(
                record.usage.provider_requests for record in self.case_records
            ),
            external_requests=sum(
                record.usage.external_requests for record in self.case_records
            ),
            recorded_tokens=sum(
                record.usage.recorded_tokens for record in self.case_records
            ),
            elapsed_seconds=sum(
                record.usage.elapsed_seconds for record in self.case_records
            ),
            estimated_cost=sum(
                (record.usage.estimated_cost for record in self.case_records),
                Decimal(0),
            ),
            currency="USD",
            cost_kind=CostKind.ESTIMATED,
        )
        if self.usage != expected:
            raise ValueError("run usage must equal exact case-record totals")

        budget = self.request.budget
        over_budget = (
            self.usage.provider_requests > budget.maximum_provider_requests
            or self.usage.external_requests > budget.maximum_external_requests
            or self.usage.recorded_tokens > budget.maximum_recorded_tokens
            or self.usage.elapsed_seconds > budget.maximum_elapsed_seconds
            or self.usage.estimated_cost > budget.maximum_estimated_cost
        )
        if self.budget_exhausted != over_budget:
            raise ValueError("budget exhausted must match exact phase usage")

        if self.status is Stage9DevelopmentRunStatus.READY:
            if (
                self.case_records
                or self.budget_exhausted
                or self.stop_reason is not None
            ):
                raise ValueError("ready result must not contain execution output")
        elif self.status is Stage9DevelopmentRunStatus.COMPLETED:
            if len(self.case_records) != 4 or self.budget_exhausted:
                raise ValueError("completed run requires all four cases within budget")
            if self.stop_reason is not None:
                raise ValueError("completed run must not contain a stop reason")
        elif self.stop_reason is None or not self.stop_reason.strip():
            raise ValueError("non-completed terminal result requires a stop reason")
        return self
