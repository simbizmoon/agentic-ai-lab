"""Deterministic reciprocal-rank fusion for retrieval result channels."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.document_chunk import DocumentChunk
from app.schemas.hybrid_retrieval import (
    HybridRetrievalMatch,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult


class DeterministicHybridRetrieverError(ValueError):
    """Raised when ranked channel inputs cannot be fused safely."""


@dataclass
class _Candidate:
    chunk: DocumentChunk
    keyword: RetrievalResult | None = None
    semantic: RetrievalResult | None = None


class DeterministicHybridRetriever:
    """Fuse keyword and semantic ranks using equal-weight RRF."""

    def fuse(
        self,
        *,
        keyword_results: Sequence[RetrievalResult],
        semantic_results: Sequence[RetrievalResult],
        request: HybridRetrievalRequest,
    ) -> HybridRetrievalResponse:
        """Return a provenance-safe union ordered by reciprocal-rank score."""

        if not isinstance(request, HybridRetrievalRequest):
            raise TypeError("request must be a HybridRetrievalRequest")
        keyword = self._validate_channel(
            keyword_results,
            name="keyword",
            require_nonnegative_score=True,
        )
        semantic = self._validate_channel(
            semantic_results,
            name="semantic",
            require_nonnegative_score=False,
        )

        candidates: dict[str, _Candidate] = {}
        for result in keyword:
            identity = result.chunk.chunk_id.casefold()
            candidates[identity] = _Candidate(
                chunk=result.chunk,
                keyword=result,
            )
        for result in semantic:
            identity = result.chunk.chunk_id.casefold()
            candidate = candidates.get(identity)
            if candidate is None:
                candidates[identity] = _Candidate(
                    chunk=result.chunk,
                    semantic=result,
                )
                continue
            if candidate.chunk != result.chunk:
                raise DeterministicHybridRetrieverError(
                    "retrieval channels contain conflicting chunks for the same chunk ID"
                )
            candidate.semantic = result

        scored = [
            self._build_match(candidate, request) for candidate in candidates.values()
        ]
        scored.sort(
            key=lambda item: (
                -item.fused_score,
                item.retrieval.chunk.chunk_id,
            )
        )
        selected = scored[: request.top_k]
        ranked = [
            item.model_copy(
                update={"retrieval": item.retrieval.model_copy(update={"rank": rank})}
            )
            for rank, item in enumerate(selected, start=1)
        ]
        return HybridRetrievalResponse(
            request=request,
            keyword_result_count=len(keyword),
            semantic_result_count=len(semantic),
            unique_chunk_count=len(candidates),
            matches=ranked,
        )

    @staticmethod
    def _validate_channel(
        values: Sequence[RetrievalResult],
        *,
        name: str,
        require_nonnegative_score: bool,
    ) -> list[RetrievalResult]:
        if isinstance(values, (str, bytes)):
            raise TypeError(f"{name}_results must be a sequence of RetrievalResult")
        results = list(values)
        if not all(isinstance(item, RetrievalResult) for item in results):
            raise TypeError(f"{name}_results must contain RetrievalResult values")
        ranks = [item.rank for item in results]
        if ranks != list(range(1, len(results) + 1)):
            raise DeterministicHybridRetrieverError(
                f"{name} result ranks must be contiguous from one in input order"
            )
        identities = [item.chunk.chunk_id.casefold() for item in results]
        if len(set(identities)) != len(identities):
            raise DeterministicHybridRetrieverError(
                f"{name} result chunk IDs must be unique"
            )
        if require_nonnegative_score and any(item.score < 0.0 for item in results):
            raise DeterministicHybridRetrieverError(
                "keyword result scores must not be negative"
            )
        return results

    @staticmethod
    def _build_match(
        candidate: _Candidate,
        request: HybridRetrievalRequest,
    ) -> HybridRetrievalMatch:
        keyword_rank = None if candidate.keyword is None else candidate.keyword.rank
        keyword_score = None if candidate.keyword is None else candidate.keyword.score
        semantic_rank = None if candidate.semantic is None else candidate.semantic.rank
        semantic_score = (
            None if candidate.semantic is None else candidate.semantic.score
        )
        keyword_contribution = (
            None if keyword_rank is None else 1.0 / (request.rrf_k + keyword_rank)
        )
        semantic_contribution = (
            None if semantic_rank is None else 1.0 / (request.rrf_k + semantic_rank)
        )
        fused_score = sum(
            value
            for value in (keyword_contribution, semantic_contribution)
            if value is not None
        )
        return HybridRetrievalMatch(
            retrieval=RetrievalResult(
                chunk=candidate.chunk,
                score=fused_score,
                rank=1,
            ),
            rrf_k=request.rrf_k,
            keyword_rank=keyword_rank,
            keyword_score=keyword_score,
            keyword_contribution=keyword_contribution,
            semantic_rank=semantic_rank,
            semantic_score=semantic_score,
            semantic_contribution=semantic_contribution,
            fused_score=fused_score,
            matched_channel_count=int(candidate.keyword is not None)
            + int(candidate.semantic is not None),
        )
