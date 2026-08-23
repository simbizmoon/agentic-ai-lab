"""Schemas for exact scholarly whole-abstract evidence adaptation."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.scholarly_document_adaptation import ScholarlyDocumentAdaptation


class ScholarlyEvidenceAdaptation(BaseModel):
    """Document adaptation paired with its exact evidence set."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    document_adaptation: ScholarlyDocumentAdaptation
    evidence_set: ResearchEvidenceSet

    @model_validator(mode="after")
    def validate_adaptation(self) -> Self:
        if self.evidence_set.document_set != self.document_adaptation.document_set:
            raise ValueError("evidence document set must match document adaptation")
        if self.evidence_set.request_id != (
            self.document_adaptation.artifact.result.request.request_id
        ):
            raise ValueError("evidence request_id must match scholarly request")
        if len(self.evidence_set.evidence) != len(
            self.document_adaptation.document_set.documents
        ):
            raise ValueError("each scholarly abstract document requires one evidence")
        return self
