"""Set-level adapters for pipeline source search and reading."""

from __future__ import annotations

from app.research.research_source_reader import (
    ResearchSourceReader,
)
from app.research.research_source_search_tool import (
    ResearchSourceSearchTool,
)
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)


class PipelineSourceSearchAdapter:
    """Run a single-query search tool across a query set."""

    def __init__(
        self,
        search_tool: ResearchSourceSearchTool,
    ) -> None:
        self._search_tool = search_tool

    @property
    def search_tool(self) -> ResearchSourceSearchTool:
        """Return the wrapped search tool."""

        return self._search_tool

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        """Search all queries and return unique candidates."""

        candidates: list[ResearchSourceCandidate] = []
        seen_source_ids: set[str] = set()

        for query in query_set.queries:
            result = self._search_tool.search(query)

            for candidate in result.candidates:
                source_key = (
                    candidate.source_id.strip().casefold()
                )

                if source_key in seen_source_ids:
                    continue

                seen_source_ids.add(source_key)
                candidates.append(candidate)

        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=candidates,
        )


class PipelineSourceReaderAdapter:
    """Run a single-candidate reader across a candidate set."""

    def __init__(
        self,
        reader: ResearchSourceReader,
    ) -> None:
        self._reader = reader

    @property
    def reader(self) -> ResearchSourceReader:
        """Return the wrapped source reader."""

        return self._reader

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        """Read every candidate and return one document set."""

        documents: list[ResearchSourceDocument] = [
            self._reader.read(candidate)
            for candidate in candidate_set.candidates
        ]

        return ResearchSourceDocumentSet(
            request_id=candidate_set.request_id,
            documents=documents,
        )
