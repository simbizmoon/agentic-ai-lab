"""Deterministic text Chunking for document retrieval."""

from __future__ import annotations

from typing import Any

from app.schemas.document_chunk import DocumentChunk


class DocumentChunkingError(ValueError):
    """Raised when document Chunking input is invalid."""


def chunk_document_text(
    *,
    document_id: str,
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Split document text into overlapping character Chunks.

    The original text is preserved exactly. No whitespace is removed
    or normalized, so character positions remain traceable to the
    source document.
    """

    if not document_id.strip():
        raise DocumentChunkingError(
            "document_id must not be blank"
        )

    if not text:
        raise DocumentChunkingError(
            "document text must not be empty"
        )

    if not text.strip():
        raise DocumentChunkingError(
            "document text must not be blank"
        )

    if chunk_size <= 0:
        raise DocumentChunkingError(
            "chunk_size must be greater than zero"
        )

    if chunk_overlap < 0:
        raise DocumentChunkingError(
            "chunk_overlap must not be negative"
        )

    if chunk_overlap >= chunk_size:
        raise DocumentChunkingError(
            "chunk_overlap must be smaller than chunk_size"
        )

    shared_metadata = dict(metadata or {})
    chunks: list[DocumentChunk] = []

    start_char = 0
    ordinal = 0

    while start_char < len(text):
        end_char = min(
            start_char + chunk_size,
            len(text),
        )
        chunk_text = text[start_char:end_char]

        chunks.append(
            DocumentChunk(
                document_id=document_id,
                chunk_id=(
                    f"{document_id}:chunk:{ordinal:04d}"
                ),
                ordinal=ordinal,
                text=chunk_text,
                start_char=start_char,
                end_char=end_char,
                metadata=dict(shared_metadata),
            )
        )

        if end_char == len(text):
            break

        start_char = end_char - chunk_overlap
        ordinal += 1

    return chunks


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Return nonblank paragraph ranges including source positions."""

    spans: list[tuple[int, int]] = []
    cursor = 0

    for part in text.split("\n\n"):
        part_start = cursor
        part_end = part_start + len(part)

        if part.strip():
            spans.append((part_start, part_end))

        cursor = part_end + 2

    return spans


def chunk_document_by_paragraphs(
    *,
    document_id: str,
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Split text while preferring paragraph boundaries.

    Consecutive paragraphs are grouped while the resulting Chunk stays
    within chunk_size. A paragraph longer than chunk_size is divided
    with the deterministic character Chunker.
    """

    if not document_id.strip():
        raise DocumentChunkingError(
            "document_id must not be blank"
        )

    if not text:
        raise DocumentChunkingError(
            "document text must not be empty"
        )

    if not text.strip():
        raise DocumentChunkingError(
            "document text must not be blank"
        )

    if chunk_size <= 0:
        raise DocumentChunkingError(
            "chunk_size must be greater than zero"
        )

    if chunk_overlap < 0:
        raise DocumentChunkingError(
            "chunk_overlap must not be negative"
        )

    if chunk_overlap >= chunk_size:
        raise DocumentChunkingError(
            "chunk_overlap must be smaller than chunk_size"
        )

    shared_metadata = dict(metadata or {})
    chunks: list[DocumentChunk] = []
    spans = _paragraph_spans(text)

    current_start: int | None = None
    current_end: int | None = None

    def append_chunk(
        *,
        start_char: int,
        end_char: int,
    ) -> None:
        ordinal = len(chunks)

        chunks.append(
            DocumentChunk(
                document_id=document_id,
                chunk_id=(
                    f"{document_id}:chunk:{ordinal:04d}"
                ),
                ordinal=ordinal,
                text=text[start_char:end_char],
                start_char=start_char,
                end_char=end_char,
                metadata=dict(shared_metadata),
            )
        )

    for paragraph_start, paragraph_end in spans:
        paragraph_length = paragraph_end - paragraph_start

        if paragraph_length > chunk_size:
            if (
                current_start is not None
                and current_end is not None
            ):
                append_chunk(
                    start_char=current_start,
                    end_char=current_end,
                )
                current_start = None
                current_end = None

            paragraph_text = text[
                paragraph_start:paragraph_end
            ]
            subchunks = chunk_document_text(
                document_id=document_id,
                text=paragraph_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metadata=shared_metadata,
            )

            for subchunk in subchunks:
                append_chunk(
                    start_char=(
                        paragraph_start
                        + subchunk.start_char
                    ),
                    end_char=(
                        paragraph_start
                        + subchunk.end_char
                    ),
                )

            continue

        if current_start is None:
            current_start = paragraph_start
            current_end = paragraph_end
            continue

        candidate_length = paragraph_end - current_start

        if candidate_length <= chunk_size:
            current_end = paragraph_end
            continue

        if current_end is None:
            raise RuntimeError(
                "current paragraph range is incomplete"
            )

        append_chunk(
            start_char=current_start,
            end_char=current_end,
        )

        current_start = paragraph_start
        current_end = paragraph_end

    if (
        current_start is not None
        and current_end is not None
    ):
        append_chunk(
            start_char=current_start,
            end_char=current_end,
        )

    return chunks
