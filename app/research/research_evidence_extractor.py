"""Port for research evidence extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)


class ResearchEvidenceExtractor(ABC):
    """Extract traceable evidence from source documents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique extractor name."""

    @abstractmethod
    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        """Extract evidence from one source document."""
