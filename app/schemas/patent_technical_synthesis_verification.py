"""Schemas for patent technical synthesis support verification."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.semantic_citation_judgment import SemanticCitationSupportLevel


class PatentTechnicalSummaryVerification(BaseModel):
    """Support verification for one synthesized patent finding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    finding_id: str
    evidence_id: str
    decision: ResearchCitationDecision
    support_level: SemanticCitationSupportLevel
    entailment_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    issues: list[str] = Field(default_factory=list)
    response_id: str

    @model_validator(mode="after")
    def validate_verification(self) -> Self:
        for name, value in {
            "finding_id": self.finding_id,
            "evidence_id": self.evidence_id,
            "rationale": self.rationale,
            "response_id": self.response_id,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        if any(not issue.strip() for issue in self.issues):
            raise ValueError("issues must not contain blank values")

        expected = {
            SemanticCitationSupportLevel.FULLY_SUPPORTED: ResearchCitationDecision.VERIFIED,
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: (
                ResearchCitationDecision.NEEDS_REVISION
            ),
            SemanticCitationSupportLevel.UNSUPPORTED: ResearchCitationDecision.REJECTED,
            SemanticCitationSupportLevel.CONTRADICTED: ResearchCitationDecision.REJECTED,
        }[self.support_level]

        if self.decision is not expected:
            raise ValueError("decision must match semantic support_level")

        return self


class PatentTechnicalOverallSummaryVerification(BaseModel):
    """Support verification for the report-level synthesized summary."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    decision: ResearchCitationDecision
    support_level: SemanticCitationSupportLevel | None = None
    entailment_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    issues: list[str] = Field(default_factory=list)
    response_id: str | None = None
    deterministic: bool = False

    @model_validator(mode="after")
    def validate_verification(self) -> Self:
        if not self.rationale.strip():
            raise ValueError("rationale must not be blank")

        if self.deterministic:
            if self.support_level is not None or self.response_id is not None:
                raise ValueError(
                    "deterministic overall verification must not have model fields"
                )
            if self.decision is not ResearchCitationDecision.VERIFIED:
                raise ValueError("deterministic overall verification must be verified")
            if self.entailment_score != 1.0:
                raise ValueError(
                    "deterministic overall verification must use score 1.0"
                )
            return self

        if self.support_level is None:
            raise ValueError("semantic overall verification requires support_level")
        if self.response_id is None or not self.response_id.strip():
            raise ValueError("semantic overall verification requires response_id")

        expected = {
            SemanticCitationSupportLevel.FULLY_SUPPORTED: ResearchCitationDecision.VERIFIED,
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: (
                ResearchCitationDecision.NEEDS_REVISION
            ),
            SemanticCitationSupportLevel.UNSUPPORTED: ResearchCitationDecision.REJECTED,
            SemanticCitationSupportLevel.CONTRADICTED: ResearchCitationDecision.REJECTED,
        }[self.support_level]
        if self.decision is not expected:
            raise ValueError("decision must match semantic support_level")

        return self


class PatentTechnicalSynthesisVerificationResult(BaseModel):
    """Verification result for all synthesized patent technical prose."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_id: str
    report_id: str
    finding_verifications: list[PatentTechnicalSummaryVerification] = Field(
        default_factory=list
    )
    overall_verification: PatentTechnicalOverallSummaryVerification
    accepted: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        if not self.report_id.strip():
            raise ValueError("report_id must not be blank")

        finding_ids = [
            item.finding_id.strip().casefold() for item in self.finding_verifications
        ]
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("finding verification IDs must be unique")

        expected = (
            self.overall_verification.decision is ResearchCitationDecision.VERIFIED
            and all(
                item.decision is ResearchCitationDecision.VERIFIED
                for item in self.finding_verifications
            )
        )
        if self.accepted is not expected:
            raise ValueError("accepted must match all verification decisions")

        return self
