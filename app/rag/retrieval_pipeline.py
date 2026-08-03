"""Integrated document retrieval and context-building pipeline."""

from __future__ import annotations

import math

from app.rag.context_builder import build_rag_context
from app.rag.document_retriever import (
    DocumentRetriever,
    DocumentRetrieverError,
)
from app.schemas.retrieval_pipeline_result import (
    RetrievalPipelineResult,
)


class RetrievalPipelineError(ValueError):
    """Raised when retrieval pipeline input is invalid."""


class RetrievalPipeline:
    """Retrieve document Chunks and build grounded LLM context."""

    def __init__(
        self,
        *,
        retriever: DocumentRetriever,
    ) -> None:
        self._retriever = retriever

    @property
    def retriever(self) -> DocumentRetriever:
        """Return the configured document Retriever."""

        return self._retriever

    def run(
        self,
        *,
        query: str,
        top_k: int = 5,
        minimum_score: float | None = None,
    ) -> RetrievalPipelineResult:
        """Retrieve related Chunks and build grounded context."""

        if not query.strip():
            raise RetrievalPipelineError(
                "retrieval query must not be blank"
            )

        if top_k <= 0:
            raise RetrievalPipelineError(
                "top_k must be greater than zero"
            )

        if (
            minimum_score is not None
            and not math.isfinite(minimum_score)
        ):
            raise RetrievalPipelineError(
                "minimum_score must be finite"
            )

        try:
            results = self.retriever.retrieve(
                query=query,
                top_k=top_k,
            )
        except DocumentRetrieverError as exc:
            raise RetrievalPipelineError(
                str(exc)
            ) from exc

        context = build_rag_context(
            results,
            minimum_score=minimum_score,
        )

        return RetrievalPipelineResult(
            query=query,
            results=results,
            context=context,
        )
