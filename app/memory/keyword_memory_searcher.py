"""Keyword-based retrieval of relevant agent memories."""

from __future__ import annotations

from app.memory.memory_relevance_scorer import (
    MemoryRelevanceScorer,
)
from app.memory.memory_service import MemoryService
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_search import (
    MemorySearchRequest,
)
from app.schemas.memory_search_result import (
    MemorySearchResult,
)


class KeywordMemorySearcher:
    """Retrieve and rank memories using deterministic keywords."""

    def __init__(
        self,
        *,
        memory_service: MemoryService,
        scorer: MemoryRelevanceScorer | None = None,
    ) -> None:
        self._memory_service = memory_service
        self._scorer = (
            scorer or MemoryRelevanceScorer()
        )

    @property
    def memory_service(self) -> MemoryService:
        """Return the configured memory service."""

        return self._memory_service

    @property
    def scorer(self) -> MemoryRelevanceScorer:
        """Return the configured relevance scorer."""

        return self._scorer

    def search(
        self,
        request: MemorySearchRequest,
    ) -> list[MemorySearchResult]:
        """Return memories ranked by relevance."""

        memories = self.memory_service.list(
            query=MemoryQuery(
                kinds=request.kinds or [],
                scopes=request.scopes or [],
                sources=request.sources or [],
                subject_id=request.subject_id,
                project_id=request.project_id,
                session_id=request.session_id,
                include_expired=request.include_expired,
            )
        )

        results: list[MemorySearchResult] = []

        for memory in memories:
            scored = self.scorer.score(
                query=request.query,
                memory=memory,
            )

            if scored.score < request.minimum_score:
                continue

            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=scored.score,
                    matched_terms=scored.matched_terms,
                    breakdown=scored.breakdown,
                )
            )

        results.sort(
            key=lambda result: (
                -result.score,
                -result.memory.importance,
                -result.memory.confidence,
                -result.memory.updated_at.timestamp(),
                result.memory.memory_id,
            )
        )

        return results[: request.limit]
