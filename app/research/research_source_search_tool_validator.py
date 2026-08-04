"""Deterministic validation for source search tools."""

from __future__ import annotations

from app.research.research_source_search_tool import (
    ResearchSourceSearchTool,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchResult,
)


class ResearchSourceSearchToolValidator:
    """Validate source search tool identity and output."""

    def validate_tool(
        self,
        tool: ResearchSourceSearchTool,
    ) -> None:
        """Validate static tool identity."""

        if not tool.name.strip():
            raise ValueError(
                "search tool name must not be blank"
            )

        if not tool.provider.strip():
            raise ValueError(
                "search tool provider must not be blank"
            )

    def validate_result(
        self,
        *,
        tool: ResearchSourceSearchTool,
        query: ResearchSearchQuery,
        result: ResearchSourceSearchResult,
    ) -> None:
        """Validate one tool result against its invocation."""

        self.validate_tool(tool)

        if result.query != query:
            raise ValueError(
                "search result query must match "
                "the invoked query"
            )

        if (
            result.provider.strip().casefold()
            != tool.provider.strip().casefold()
        ):
            raise ValueError(
                "search result provider must match "
                "the tool provider"
            )
