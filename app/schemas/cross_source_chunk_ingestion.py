"""Contracts for provenance-safe cross-source chunk ingestion."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_chunk import DocumentChunk
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_document import (
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


class CrossSourceChunkProvenance(BaseModel):
    """Exact source and document identity carried by one chunk."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    source_type: ResearchSourceType
    start_character: int = Field(ge=0)
    end_character: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_character <= self.start_character:
            raise ValueError("end_character must be greater than start_character")
        return self


class CrossSourceChunkIngestionResult(BaseModel):
    """Validated chunks derived from a heterogeneous document set."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_id: str = Field(min_length=1)
    document_set: ResearchSourceDocumentSet
    chunks: list[DocumentChunk] = Field(default_factory=list)
    provenance: list[CrossSourceChunkProvenance] = Field(default_factory=list)
    failed_document_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ingestion(self) -> Self:
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        if self.document_set.request_id != self.request_id:
            raise ValueError("document set request_id must match ingestion request_id")

        documents = {
            item.document_id.strip().casefold(): item
            for item in self.document_set.documents
        }
        chunk_ids = [item.chunk_id.strip().casefold() for item in self.chunks]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("chunk IDs must be unique")

        provenance_ids = [item.chunk_id.strip().casefold() for item in self.provenance]
        if len(set(provenance_ids)) != len(provenance_ids):
            raise ValueError("provenance chunk IDs must be unique")
        if set(chunk_ids) != set(provenance_ids):
            raise ValueError("every chunk must have exactly one provenance record")

        provenance_by_chunk = {
            item.chunk_id.strip().casefold(): item for item in self.provenance
        }
        ordinals_by_document: dict[str, list[int]] = {}
        read_document_ids: set[str] = set()

        for chunk in self.chunks:
            document_key = chunk.document_id.strip().casefold()
            document = documents.get(document_key)
            if document is None:
                raise ValueError("all chunks must reference existing documents")
            if document.status is not ResearchSourceDocumentStatus.READ:
                raise ValueError("chunks cannot reference failed documents")
            if chunk.end_char > len(document.content):
                raise ValueError(
                    "chunk character range must be within document content"
                )
            if document.content[chunk.start_char : chunk.end_char] != chunk.text:
                raise ValueError(
                    "chunk text must match the exact document character range"
                )

            link = provenance_by_chunk[chunk.chunk_id.strip().casefold()]
            if link.document_id != chunk.document_id:
                raise ValueError("provenance document_id must match chunk document_id")
            if link.source_id != document.candidate.source_id:
                raise ValueError("provenance source_id must match document source_id")
            if link.source_type is not document.candidate.source_type:
                raise ValueError(
                    "provenance source_type must match document source_type"
                )
            if (link.start_character, link.end_character) != (
                chunk.start_char,
                chunk.end_char,
            ):
                raise ValueError("provenance range must match chunk character range")

            read_document_ids.add(document_key)
            ordinals_by_document.setdefault(document_key, []).append(chunk.ordinal)

        for ordinals in ordinals_by_document.values():
            if sorted(ordinals) != list(range(len(ordinals))):
                raise ValueError(
                    "chunk ordinals must be contiguous from zero per document"
                )

        expected_failed = {
            item.document_id.strip().casefold()
            for item in self.document_set.failed_documents()
        }
        supplied_failed = [item.strip().casefold() for item in self.failed_document_ids]
        if any(not item.strip() for item in self.failed_document_ids):
            raise ValueError("failed_document_ids must not contain blank values")
        if len(set(supplied_failed)) != len(supplied_failed):
            raise ValueError("failed_document_ids must be unique")
        if set(supplied_failed) != expected_failed:
            raise ValueError(
                "failed_document_ids must exactly identify failed documents"
            )

        expected_read = {
            item.document_id.strip().casefold()
            for item in self.document_set.successful_documents()
        }
        if read_document_ids != expected_read:
            raise ValueError("every read document must produce at least one chunk")

        return self

    def ordered_chunks(self) -> list[DocumentChunk]:
        """Return chunks in document-set and ordinal order."""

        positions = {
            item.document_id.strip().casefold(): position
            for position, item in enumerate(self.document_set.documents)
        }
        return sorted(
            self.chunks,
            key=lambda item: (
                positions[item.document_id.strip().casefold()],
                item.ordinal,
            ),
        )
