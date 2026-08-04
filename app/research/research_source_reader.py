"""Port for research source document readers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)


class ResearchSourceReader(ABC):
    """Read source candidates into normalized documents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique reader name."""

    @abstractmethod
    def read(
        self,
        candidate: ResearchSourceCandidate,
    ) -> ResearchSourceDocument:
        """Read one source candidate."""
