"""Deterministic ingestion of heterogeneous research documents into chunks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.rag.document_chunker import chunk_document_by_paragraphs
from app.schemas.cross_source_chunk_ingestion import (
    CrossSourceChunkIngestionResult,
    CrossSourceChunkProvenance,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.research_source_document import ResearchSourceDocumentSet

Chunker = Callable[..., list[DocumentChunk]]


class CrossSourceChunkIngestionRuntime:
    """Chunk all readable documents without making external requests."""

    def __init__(
        self,
        *,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        chunker: Chunker = chunk_document_by_paragraphs,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must not be negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._chunker = chunker

    def ingest(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
    ) -> CrossSourceChunkIngestionResult:
        """Create exact chunks and provenance in document-set order."""

        chunks: list[DocumentChunk] = []
        provenance: list[CrossSourceChunkProvenance] = []

        for document in document_set.successful_documents():
            candidate = document.candidate
            metadata: dict[str, Any] = {
                "request_id": document_set.request_id,
                "task_id": candidate.task_id,
                "source_id": candidate.source_id,
                "source_type": candidate.source_type.value,
            }
            document_chunks = self._chunker(
                document_id=document.document_id,
                text=document.content,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
                metadata=metadata,
            )

            for chunk in document_chunks:
                chunks.append(chunk)
                provenance.append(
                    CrossSourceChunkProvenance(
                        chunk_id=chunk.chunk_id,
                        source_id=candidate.source_id,
                        document_id=document.document_id,
                        source_type=candidate.source_type,
                        start_character=chunk.start_char,
                        end_character=chunk.end_char,
                    )
                )

        return CrossSourceChunkIngestionResult(
            request_id=document_set.request_id,
            document_set=document_set,
            chunks=chunks,
            provenance=provenance,
            failed_document_ids=[
                document.document_id for document in document_set.failed_documents()
            ],
        )
