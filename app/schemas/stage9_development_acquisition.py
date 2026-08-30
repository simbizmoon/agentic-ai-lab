"""Leakage-safe contracts for Stage 9 development evidence acquisition."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
)
from app.schemas.stage9_evaluation_manifest import (
    Stage9DatasetPartition,
    Stage9EvaluationCase,
    Stage9EvaluationDomain,
)


class Stage9AcquisitionChannel(StrEnum):
    OFFICIAL_WEB = "official_web"
    SCHOLARLY_PRIMARY = "scholarly_primary"
    EPO_PATENT = "epo_patent"
    LOCAL_REPOSITORY = "local_repository"


class Stage9AcquisitionStatus(StrEnum):
    EVIDENCE_AVAILABLE = "evidence_available"
    NO_EVIDENCE = "no_evidence"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


CHANNELS_BY_DOMAIN = {
    Stage9EvaluationDomain.GENERAL_TECHNICAL: (Stage9AcquisitionChannel.OFFICIAL_WEB,),
    Stage9EvaluationDomain.ACADEMIC: (Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,),
    Stage9EvaluationDomain.PATENT: (Stage9AcquisitionChannel.EPO_PATENT,),
    Stage9EvaluationDomain.CROSS_SOURCE: (
        Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
        Stage9AcquisitionChannel.LOCAL_REPOSITORY,
    ),
}


class Stage9DevelopmentAcquisitionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_provider_requests: int = Field(ge=1, le=4)
    maximum_external_requests: int = Field(ge=1, le=6)
    maximum_documents: int = Field(ge=1, le=8)
    maximum_evidence_items: int = Field(ge=1, le=32)

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if self.maximum_external_requests < self.maximum_provider_requests:
            raise ValueError("external ceiling must cover provider requests")
        return self


class Stage9DevelopmentAcquisitionRequest(BaseModel):
    """Question-only runtime input; golden answers and sources are not fields."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_id: str
    case_id: str
    domain: Stage9EvaluationDomain
    question: str
    constraints: tuple[str, ...] = Field(min_length=1, max_length=32)
    channels: tuple[Stage9AcquisitionChannel, ...] = Field(min_length=1, max_length=4)
    budget: Stage9DevelopmentAcquisitionBudget

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        for field_name in ("request_id", "case_id", "question"):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        if self.case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            raise ValueError("acquisition is limited to disclosed development cases")
        if self.channels != CHANNELS_BY_DOMAIN[self.domain]:
            raise ValueError("acquisition channels must match the locked case domain")
        if any(
            not value.strip() or value != value.strip() for value in self.constraints
        ):
            raise ValueError("constraints must be normalized and nonblank")
        return self


class Stage9DevelopmentAcquisitionUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider_requests: int = Field(ge=0)
    external_requests: int = Field(ge=0)
    documents_read: int = Field(ge=0)
    evidence_items: int = Field(ge=0)


class Stage9DevelopmentAcquisitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: Stage9DevelopmentAcquisitionRequest
    status: Stage9AcquisitionStatus
    evidence_set: ResearchEvidenceSet
    usage: Stage9DevelopmentAcquisitionUsage
    failure_code: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.evidence_set.request_id != self.request.request_id:
            raise ValueError("evidence set must match the acquisition request")
        budget = self.request.budget
        if (
            self.usage.provider_requests > budget.maximum_provider_requests
            or self.usage.external_requests > budget.maximum_external_requests
            or self.usage.documents_read > budget.maximum_documents
            or self.usage.evidence_items > budget.maximum_evidence_items
        ):
            raise ValueError("acquisition usage exceeds its hard budget")
        if self.usage.external_requests < self.usage.provider_requests:
            raise ValueError("external requests must cover provider requests")
        if self.usage.documents_read != len(
            self.evidence_set.document_set.successful_documents()
        ):
            raise ValueError("document usage must match successful documents")
        if self.usage.evidence_items != len(self.evidence_set.evidence):
            raise ValueError("evidence usage must match exact evidence items")
        has_evidence = bool(self.evidence_set.evidence)
        if (
            self.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
            and not has_evidence
        ):
            raise ValueError("evidence_available requires evidence")
        if self.status is Stage9AcquisitionStatus.NO_EVIDENCE and has_evidence:
            raise ValueError("no_evidence cannot contain evidence")
        if self.status is Stage9AcquisitionStatus.FAILED:
            if self.failure_code is None or not self.failure_code.strip():
                raise ValueError("failed acquisition requires a failure code")
        elif self.failure_code is not None:
            raise ValueError("only failed acquisition may contain a failure code")
        return self


class Stage9DevelopmentAcquisitionRequestBuilder:
    """Copy only runtime-safe question boundaries from a locked case."""

    def build(
        self,
        *,
        case: Stage9EvaluationCase,
        request_id: str,
    ) -> Stage9DevelopmentAcquisitionRequest:
        if not isinstance(case, Stage9EvaluationCase):
            raise TypeError("case must be a Stage9EvaluationCase")
        case_id = case.definition.case_id
        if (
            case.partition is not Stage9DatasetPartition.DEVELOPMENT
            or case_id not in STAGE9_DEVELOPMENT_CASE_IDS
        ):
            raise ValueError("builder must not expose a blind holdout case")
        return Stage9DevelopmentAcquisitionRequest(
            request_id=request_id,
            case_id=case_id,
            domain=case.domain,
            question=case.definition.evaluation_input.research_question,
            constraints=(*case.prohibited_claims, *case.expected_uncertainties),
            channels=CHANNELS_BY_DOMAIN[case.domain],
            budget=Stage9DevelopmentAcquisitionBudget(
                maximum_provider_requests=2,
                maximum_external_requests=3,
                maximum_documents=4,
                maximum_evidence_items=16,
            ),
        )
