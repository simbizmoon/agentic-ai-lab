"""Deterministic keyword retrieval over document chunks."""

from __future__ import annotations

from collections.abc import Sequence

from app.memory.memory_tokenizer import normalize_search_text, tokenize_memory_text
from app.schemas.document_chunk import DocumentChunk
from app.schemas.keyword_retrieval import (
    KeywordRetrievalExplanation,
    KeywordRetrievalMatch,
    KeywordRetrievalRequest,
    KeywordRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult


class DeterministicKeywordRetrieverError(ValueError):
    """Raised when a keyword retrieval corpus or query is invalid."""


class DeterministicKeywordRetriever:
    """Rank chunks using transparent unique-query-token coverage."""

    def search(
        self,
        *,
        chunks: Sequence[DocumentChunk],
        request: KeywordRetrievalRequest,
    ) -> KeywordRetrievalResponse:
        """Return matching chunks ordered by score and chunk ID."""

        corpus = list(chunks)
        self._validate_unique_chunk_ids(corpus)

        query_tokens = tokenize_memory_text(request.query)
        if not query_tokens:
            raise DeterministicKeywordRetrieverError(
                "keyword retrieval query must contain at least one searchable token"
            )

        normalized_query = normalize_search_text(request.query)
        scored: list[tuple[float, str, DocumentChunk, list[str], bool]] = []

        for chunk in corpus:
            chunk_tokens = set(tokenize_memory_text(chunk.text))
            matched_terms = [token for token in query_tokens if token in chunk_tokens]
            if not matched_terms:
                continue

            token_coverage = len(matched_terms) / len(query_tokens)
            score = round(token_coverage, 6)
            if score < request.minimum_score:
                continue

            exact_phrase_match = normalized_query in normalize_search_text(chunk.text)
            scored.append(
                (
                    score,
                    chunk.chunk_id,
                    chunk,
                    matched_terms,
                    exact_phrase_match,
                )
            )

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = scored[: request.top_k]
        matches = [
            KeywordRetrievalMatch(
                retrieval=RetrievalResult(
                    chunk=chunk,
                    score=score,
                    rank=rank,
                ),
                explanation=KeywordRetrievalExplanation(
                    query_tokens=list(query_tokens),
                    matched_terms=matched_terms,
                    token_coverage=len(matched_terms) / len(query_tokens),
                    exact_phrase_match=exact_phrase_match,
                ),
            )
            for rank, (
                score,
                _chunk_id,
                chunk,
                matched_terms,
                exact_phrase_match,
            ) in enumerate(selected, start=1)
        ]

        return KeywordRetrievalResponse(
            request=request,
            corpus_chunk_count=len(corpus),
            matches=matches,
        )

    @staticmethod
    def _validate_unique_chunk_ids(chunks: list[DocumentChunk]) -> None:
        normalized_ids = [chunk.chunk_id.strip().casefold() for chunk in chunks]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise DeterministicKeywordRetrieverError(
                "keyword retrieval corpus chunk IDs must be unique"
            )
