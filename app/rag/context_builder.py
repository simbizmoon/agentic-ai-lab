"""Build grounded LLM context from retrieval results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)
from app.schemas.retrieval_result import RetrievalResult


class RagContextBuilderError(ValueError):
    """Raised when retrieval context cannot be constructed."""


def _source_from_metadata(
    metadata: dict[str, Any],
) -> str | None:
    """Return a human-readable source from Chunk metadata."""

    for key in ("source", "filename", "title"):
        value = metadata.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def build_rag_context(
    results: Sequence[RetrievalResult],
    *,
    minimum_score: float | None = None,
) -> RagContext:
    """Convert retrieval results into grounded context blocks."""

    selected_results = [
        result
        for result in results
        if (
            minimum_score is None
            or result.score >= minimum_score
        )
    ]

    if not selected_results:
        return RagContext(
            context_text="",
            citations=[],
        )

    ordered_results = sorted(
        selected_results,
        key=lambda result: (
            result.rank,
            result.chunk.chunk_id,
        ),
    )

    context_blocks: list[str] = []
    citations: list[RagCitation] = []

    for position, result in enumerate(
        ordered_results,
        start=1,
    ):
        citation_id = f"S{position}"
        chunk = result.chunk
        source = _source_from_metadata(
            chunk.metadata
        )

        citation = RagCitation(
            citation_id=citation_id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            rank=result.rank,
            score=result.score,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            source=source,
        )
        citations.append(citation)

        header_parts = [
            f"[{citation_id}]",
            f"document_id={chunk.document_id}",
            f"chunk_id={chunk.chunk_id}",
            f"score={result.score:.6f}",
        ]

        if source is not None:
            header_parts.append(
                f"source={source}"
            )

        context_blocks.append(
            "\n".join(
                [
                    " | ".join(header_parts),
                    chunk.text,
                ]
            )
        )

    return RagContext(
        context_text="\n\n".join(context_blocks),
        citations=citations,
    )
