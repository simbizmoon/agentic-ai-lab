"""Deterministic federation of Web and Local set-level source searchers."""

from __future__ import annotations

from itertools import zip_longest

from app.research.single_research_agent_pipeline import ResearchSourceSearcherProtocol
from app.schemas.research_search_budget import ResearchSearchUsage
from app.schemas.research_search_query import ResearchSearchQuerySet
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)


class FederatedResearchSourceSearcher:
    """Interleave compatible Web and Local candidate sets."""

    def __init__(
        self,
        *,
        web_searcher: ResearchSourceSearcherProtocol,
        local_searcher: ResearchSourceSearcherProtocol,
    ) -> None:
        self._web_searcher = web_searcher
        self._local_searcher = local_searcher

    @property
    def search_usage(self) -> ResearchSearchUsage:
        """Expose Web provider usage without counting Local retrieval."""
        usage = getattr(self._web_searcher, "search_usage", None)
        return usage if usage is not None else ResearchSearchUsage()

    @property
    def search_budget(self) -> object | None:
        """Expose the Web provider budget when available."""
        return getattr(self._web_searcher, "search_budget", None)

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        """Search both universes and deterministically merge candidates."""
        web_result = self._web_searcher.search(query_set)
        local_result = self._local_searcher.search(query_set)
        self._validate_child_result("web", web_result, query_set)
        self._validate_child_result("local", local_result, query_set)

        merged: list[ResearchSourceCandidate] = []
        seen_source_ids: set[str] = set()

        for query in query_set.ordered_queries():
            seen_urls: set[str] = set()
            next_rank = 1
            pairs = zip_longest(
                web_result.candidates_for_query(query.query_id),
                local_result.candidates_for_query(query.query_id),
            )
            for web_candidate, local_candidate in pairs:
                for candidate in (web_candidate, local_candidate):
                    if candidate is None:
                        continue
                    source_key = candidate.source_id.strip().casefold()
                    url_key = candidate.normalized_url()
                    if source_key in seen_source_ids or url_key in seen_urls:
                        continue
                    seen_source_ids.add(source_key)
                    seen_urls.add(url_key)
                    merged.append(candidate.model_copy(update={"rank": next_rank}))
                    next_rank += 1

        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=merged,
        )

    @staticmethod
    def _validate_child_result(
        child_name: str,
        result: ResearchSourceCandidateSet,
        query_set: ResearchSearchQuerySet,
    ) -> None:
        if result.request_id != query_set.request_id:
            raise ValueError(f"{child_name} candidate set request_id does not match")
        if result.query_set != query_set:
            raise ValueError(f"{child_name} candidate set query_set does not match")
