"""Explicit-origin routing for research source readers."""

from __future__ import annotations

from app.research.research_source_reader import ResearchSourceReader
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import ResearchSourceDocument


class RoutingResearchSourceReader(ResearchSourceReader):
    """Route candidates to Web or Local readers by explicit origin."""

    def __init__(
        self,
        *,
        web_reader: ResearchSourceReader,
        local_reader: ResearchSourceReader,
    ) -> None:
        self._web_reader = web_reader
        self._local_reader = local_reader

    @property
    def name(self) -> str:
        return "routing-research-source-reader"

    def read(self, candidate: ResearchSourceCandidate) -> ResearchSourceDocument:
        origin = candidate.metadata.get("research_origin")
        if origin == "web":
            return self._web_reader.read(candidate)
        if origin == "local":
            return self._local_reader.read(candidate)
        if origin is None:
            raise ValueError("research source candidate is missing research_origin")
        raise ValueError(f"unsupported research_origin: {origin}")
