"""Schemas for bounded patent technical-relevance reports."""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
)


class PatentTechnicalEvidenceReference(BaseModel):
    """Exact evidence provenance used by one patent technical finding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    evidence_id: str
    source_id: str
    document_id: str
    excerpt: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        required = {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "excerpt": self.excerpt,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.end_character <= self.start_character:
            raise ValueError("end_character must be greater than start_character")
        return self


class PatentTechnicalFinding(BaseModel):
    """One evidence-grounded technical-relevance finding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    finding_id: str
    publication_number: str
    title: str
    source_url: str
    publication_date: date | None = None
    source_family: PatentSourceFamily
    metadata_verification_state: PatentMetadataVerificationState
    relevance_level: EvidenceRelevanceLevel
    relevance_score: float = Field(ge=0.0, le=1.0)
    relevance_rationale: str
    evidence: PatentTechnicalEvidenceReference
    abstract_language: str | None = None

    @model_validator(mode="after")
    def validate_finding(self) -> Self:
        required = {
            "finding_id": self.finding_id,
            "publication_number": self.publication_number,
            "title": self.title,
            "source_url": self.source_url,
            "relevance_rationale": self.relevance_rationale,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        if self.relevance_level not in {
            EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
        }:
            raise ValueError(
                "patent technical findings require a completed relevant judgment"
            )

        if self.abstract_language is not None and not self.abstract_language.strip():
            raise ValueError("abstract_language must not be blank when provided")

        return self


class PatentTechnicalResearchReport(BaseModel):
    """Deterministic bounded report over patent relevance evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    report_id: str
    request_id: str
    task_id: str
    question: str
    objective: str
    prior_art_cutoff_date: date | None = None
    title: str
    findings: list[PatentTechnicalFinding] = Field(default_factory=list)
    unevaluated_evidence_ids: list[str] = Field(default_factory=list)
    finding_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    verified_record_count: int = Field(ge=0)
    input_evidence_count: int = Field(ge=0)
    executed_query_purpose: str
    executed_cql: str
    scope_notice: str
    builder: str

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        required = {
            "report_id": self.report_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "question": self.question,
            "objective": self.objective,
            "title": self.title,
            "executed_query_purpose": self.executed_query_purpose,
            "executed_cql": self.executed_cql,
            "scope_notice": self.scope_notice,
            "builder": self.builder,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        finding_ids = [
            finding.finding_id.strip().casefold() for finding in self.findings
        ]
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("finding IDs must be unique")

        evidence_ids = [
            finding.evidence.evidence_id.strip().casefold() for finding in self.findings
        ]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("finding evidence IDs must be unique")

        unevaluated = [
            value.strip().casefold() for value in self.unevaluated_evidence_ids
        ]
        if any(not value for value in unevaluated):
            raise ValueError("unevaluated_evidence_ids must not contain blanks")
        if len(set(unevaluated)) != len(unevaluated):
            raise ValueError("unevaluated_evidence_ids must not contain duplicates")
        if set(evidence_ids) & set(unevaluated):
            raise ValueError("evaluated and unevaluated evidence IDs must not overlap")

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must match findings")

        unique_sources = {
            finding.evidence.source_id.strip().casefold() for finding in self.findings
        }
        if self.source_count != len(unique_sources):
            raise ValueError("source_count must match unique finding sources")

        if self.source_count > self.document_count:
            raise ValueError("source_count must not exceed document_count")

        if self.input_evidence_count != self.finding_count + len(
            self.unevaluated_evidence_ids
        ):
            raise ValueError(
                "input_evidence_count must equal findings plus unevaluated evidence"
            )

        return self
