"""Schemas for adapting scholarly abstracts into research documents."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.research_source_document import ResearchSourceDocumentSet
from app.schemas.scholarly_search_workflow import ScholarlySearchWorkflowArtifact


class ScholarlyDocumentAdaptation(BaseModel):
    """Exact document adaptation with explicit abstract omissions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    artifact: ScholarlySearchWorkflowArtifact
    document_set: ResearchSourceDocumentSet
    omitted_work_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_adaptation(self) -> Self:
        request_id = self.artifact.result.request.request_id
        if self.document_set.request_id != request_id:
            raise ValueError("document set request_id must match scholarly request")
        work_ids = {
            work.work_id.strip().casefold() for work in self.artifact.result.works
        }
        omitted = [value.strip().casefold() for value in self.omitted_work_ids]
        if any(not value for value in omitted):
            raise ValueError("omitted_work_ids must not contain blank values")
        if len(set(omitted)) != len(omitted):
            raise ValueError("omitted_work_ids must not contain duplicates")
        if not set(omitted).issubset(work_ids):
            raise ValueError("omitted_work_ids must reference accepted works")
        document_work_ids = [
            document.metadata.get("scholarly_work_id", "").strip().casefold()
            for document in self.document_set.documents
        ]
        if any(not value for value in document_work_ids):
            raise ValueError("documents must contain scholarly_work_id metadata")
        if len(set(document_work_ids)) != len(document_work_ids):
            raise ValueError("documents must reference unique scholarly works")
        if set(document_work_ids) & set(omitted):
            raise ValueError("omitted works must not have documents")
        if set(document_work_ids) | set(omitted) != work_ids:
            raise ValueError("every accepted work must be documented or omitted")
        return self
