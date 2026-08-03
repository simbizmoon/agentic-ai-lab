"""End-to-end retrieval of relevant agent memory context."""

from __future__ import annotations

from app.memory.keyword_memory_searcher import (
    KeywordMemorySearcher,
)
from app.memory.memory_context_builder import (
    MemoryContextBuilder,
)
from app.schemas.memory_context_config import (
    MemoryContextConfig,
)
from app.schemas.memory_retrieval import (
    MemoryRetrievalRequest,
)
from app.schemas.memory_retrieval_result import (
    MemoryRetrievalResult,
)
from app.schemas.memory_search import (
    MemorySearchRequest,
)


class MemoryRetrievalService:
    """Search memories and build safe prompt context."""

    def __init__(
        self,
        *,
        searcher: KeywordMemorySearcher,
    ) -> None:
        self._searcher = searcher

    @property
    def searcher(self) -> KeywordMemorySearcher:
        """Return the configured keyword searcher."""

        return self._searcher

    def retrieve(
        self,
        request: MemoryRetrievalRequest,
    ) -> MemoryRetrievalResult:
        """Search, select, and render relevant memory context."""

        search_results = self.searcher.search(
            MemorySearchRequest(
                query=request.query,
                limit=request.search_limit,
                minimum_score=(
                    request.minimum_search_score
                ),
                kinds=request.kinds,
                scopes=request.scopes,
                sources=request.sources,
                subject_id=request.subject_id,
                project_id=request.project_id,
                session_id=request.session_id,
                include_expired=request.include_expired,
            )
        )

        builder = MemoryContextBuilder(
            config=MemoryContextConfig(
                maximum_items=request.context_limit,
                maximum_content_characters=(
                    request.maximum_content_characters
                ),
                minimum_score=(
                    request.minimum_context_score
                ),
                include_tags=request.include_tags,
                include_source_reference=(
                    request.include_source_reference
                ),
            )
        )

        context = builder.build(
            query=request.query,
            results=search_results,
        )

        retrieved_memory_ids = [
            item.memory_id
            for item in context.items
        ]

        if request.record_access:
            self._record_access(
                retrieved_memory_ids
            )

        return MemoryRetrievalResult(
            search_results=search_results,
            context=context,
            retrieved_memory_ids=retrieved_memory_ids,
            access_recorded=request.record_access,
        )

    def _record_access(
        self,
        memory_ids: list[str],
    ) -> None:
        """Record access only for memories used in context."""

        for memory_id in memory_ids:
            self.searcher.memory_service.touch(
                memory_id
            )
