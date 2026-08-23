"""Abstract port for bounded scholarly metadata providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.scholarly_provider import (
    ScholarlySearchRequest,
    ScholarlySearchResult,
)


class ScholarlyMetadataProvider(ABC):
    """Provider-neutral scholarly metadata search boundary."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider name."""

    @abstractmethod
    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        """Execute one bounded search and return a validated result."""
