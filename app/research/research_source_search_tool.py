"""Port for research source search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchResult,
)


class ResearchSourceSearchTool(ABC):
    """Search for research sources using one provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique tool name."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the underlying search provider name."""

    @abstractmethod
    def search(
        self,
        query: ResearchSearchQuery,
    ) -> ResearchSourceSearchResult:
        """Execute one source search query."""
