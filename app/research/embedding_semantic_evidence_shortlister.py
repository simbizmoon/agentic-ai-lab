"""Embedding-based semantic shortlist for research evidence candidates."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.embedding_provider import EmbeddingProvider
from app.rag.vector_math import cosine_similarity
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceCandidate,
)


@dataclass(frozen=True)
class SemanticEvidenceShortlistItem:
    """One paragraph candidate ranked by semantic similarity."""

    candidate: ParagraphEvidenceCandidate
    semantic_score: float
    rank: int


class EmbeddingSemanticEvidenceShortlister:
    """Rank paragraph candidates against question and objective."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        maximum_candidates: int = 8,
        rrf_k: int = 60,
    ) -> None:
        if maximum_candidates < 1:
            raise ValueError(
                "maximum_candidates must be greater than zero"
            )
        if rrf_k < 1:
            raise ValueError("rrf_k must be greater than zero")

        self._embedding_provider = embedding_provider
        self._maximum_candidates = maximum_candidates
        self._rrf_k = rrf_k

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Return the configured embedding provider."""

        return self._embedding_provider

    @property
    def maximum_candidates(self) -> int:
        """Return the maximum number of shortlisted candidates."""

        return self._maximum_candidates

    @property
    def rrf_k(self) -> int:
        """Return the reciprocal-rank-fusion constant."""

        return self._rrf_k

    def shortlist(
        self,
        *,
        question: str,
        objective: str,
        candidates: list[ParagraphEvidenceCandidate],
    ) -> list[SemanticEvidenceShortlistItem]:
        """Return candidates ordered by semantic similarity."""

        normalized_question = question.strip()
        normalized_objective = objective.strip()

        if not normalized_question:
            raise ValueError("question must not be blank")
        if not normalized_objective:
            raise ValueError("objective must not be blank")
        if not candidates:
            return []

        query_text = (
            f"Question: {normalized_question}\n"
            f"Objective: {normalized_objective}"
        )

        embeddings = self._embedding_provider.embed_texts(
            [
                query_text,
                *[candidate.text for candidate in candidates],
            ]
        )

        if len(embeddings) != len(candidates) + 1:
            raise ValueError(
                "embedding provider returned an unexpected count"
            )

        query_embedding = embeddings[0]

        embedding_scores = [
            cosine_similarity(
                query_embedding.vector,
                candidate_embedding.vector,
            )
            for candidate_embedding in embeddings[1:]
        ]

        embedding_order = sorted(
            range(len(candidates)),
            key=lambda index: (
                -embedding_scores[index],
                candidates[index].start,
                candidates[index].end,
            ),
        )
        lexical_order = sorted(
            range(len(candidates)),
            key=lambda index: (
                -candidates[index].lexical_score,
                candidates[index].start,
                candidates[index].end,
            ),
        )

        embedding_rank = {
            index: rank
            for rank, index in enumerate(
                embedding_order,
                start=1,
            )
        }
        lexical_rank = {
            index: rank
            for rank, index in enumerate(
                lexical_order,
                start=1,
            )
        }

        fused_order = sorted(
            range(len(candidates)),
            key=lambda index: (
                -self._rrf_score(
                    embedding_rank=embedding_rank[index],
                    lexical_rank=lexical_rank[index],
                ),
                embedding_rank[index],
                lexical_rank[index],
                candidates[index].start,
                candidates[index].end,
            ),
        )

        selected = fused_order[: self._maximum_candidates]

        return [
            SemanticEvidenceShortlistItem(
                candidate=candidates[index],
                semantic_score=embedding_scores[index],
                rank=rank,
            )
            for rank, index in enumerate(
                selected,
                start=1,
            )
        ]

    def _rrf_score(
        self,
        *,
        embedding_rank: int,
        lexical_rank: int,
    ) -> float:
        """Fuse embedding and lexical ranks with equal-weight RRF."""

        return (
            1.0 / (self._rrf_k + embedding_rank)
            + 1.0 / (self._rrf_k + lexical_rank)
        )
