"""Schemas for bounded scholarly search-to-evidence workflow results."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scholarly_evidence_adaptation import ScholarlyEvidenceAdaptation
from app.schemas.scholarly_provider import ScholarlySearchRequest


class BoundedScholarlyEvidenceWorkflowResult(BaseModel):
    """Validated execution summary plus exact nested scholarly artifacts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: ScholarlySearchRequest
    task_id: str
    adaptation: ScholarlyEvidenceAdaptation
    maximum_provider_requests: int = Field(ge=1)
    actual_provider_requests: int = Field(ge=0)
    records_received: int = Field(ge=0)
    works_accepted: int = Field(ge=0)
    records_rejected: int = Field(ge=0)
    abstract_documents_created: int = Field(ge=0)
    works_omitted_without_abstract: int = Field(ge=0)
    whole_abstract_evidence_created: int = Field(ge=0)
    duplicate_identity_groups: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if not self.task_id.strip():
            raise ValueError("task_id must not be blank")
        artifact = self.adaptation.document_adaptation.artifact
        provider_result = artifact.result
        if provider_result.request != self.request:
            raise ValueError("nested provider request must match workflow request")
        if self.maximum_provider_requests != self.request.maximum_provider_requests:
            raise ValueError("maximum provider requests must match request budget")
        expected = {
            "actual_provider_requests": provider_result.usage.request_count,
            "records_received": provider_result.usage.records_received,
            "works_accepted": len(provider_result.works),
            "records_rejected": provider_result.usage.records_rejected,
            "abstract_documents_created": len(
                self.adaptation.document_adaptation.document_set.documents
            ),
            "works_omitted_without_abstract": len(
                self.adaptation.document_adaptation.omitted_work_ids
            ),
            "whole_abstract_evidence_created": len(
                self.adaptation.evidence_set.evidence
            ),
            "duplicate_identity_groups": len(artifact.duplicate_groups),
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must match nested artifact")
        if self.actual_provider_requests > self.maximum_provider_requests:
            raise ValueError("actual provider requests exceed request budget")
        return self
