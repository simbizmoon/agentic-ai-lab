"""Explicit-origin routing for research source quality evaluation."""

from __future__ import annotations

from app.research.single_research_agent_pipeline import (
    ResearchSourceQualityEvaluatorProtocol,
)
from app.schemas.research_source_document import ResearchSourceDocument
from app.schemas.research_source_quality import ResearchSourceQualityEvaluation


class RoutingResearchSourceQualityEvaluator:
    """Route source quality evaluation by candidate origin metadata."""

    def __init__(
        self,
        *,
        web_evaluator: ResearchSourceQualityEvaluatorProtocol,
        local_evaluator: ResearchSourceQualityEvaluatorProtocol,
    ) -> None:
        self._web_evaluator = web_evaluator
        self._local_evaluator = local_evaluator

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        origin = document.candidate.metadata.get("research_origin")
        if origin == "web":
            return self._web_evaluator.evaluate(document)
        if origin == "local":
            return self._local_evaluator.evaluate(document)
        if origin is None:
            raise ValueError("research source document is missing research_origin")
        raise ValueError(f"unsupported research_origin: {origin}")
