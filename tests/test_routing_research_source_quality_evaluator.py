"""Tests for explicit-origin source quality routing."""

from __future__ import annotations

import pytest

from app.research.routing_research_source_quality_evaluator import (
    RoutingResearchSourceQualityEvaluator,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
    ResearchSourceQualityLevel,
)


def make_document(origin: str | None) -> ResearchSourceDocument:
    metadata = {} if origin is None else {"research_origin": origin}
    item = ResearchSourceCandidate(
        source_id=f"source-{origin or 'missing'}",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title="Source",
        url=f"https://example.com/{origin or 'missing'}",
        source_type=ResearchSourceType.OTHER,
        snippet="Source content.",
        rank=1,
        metadata=metadata,
    )
    content = "Source content for quality evaluation."
    return ResearchSourceDocument(
        document_id=f"document-{item.source_id}",
        candidate=item,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
    )


class RecordingEvaluator:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[ResearchSourceDocument] = []
        self.returned: ResearchSourceQualityEvaluation | None = None

    def evaluate(
        self, document: ResearchSourceDocument
    ) -> ResearchSourceQualityEvaluation:
        self.calls.append(document)
        self.returned = ResearchSourceQualityEvaluation(
            document=document,
            evaluator=self.name,
            authority_score=0.5,
            primary_source_score=0.5,
            recency_score=0.5,
            completeness_score=0.5,
            traceability_score=0.5,
            overall_score=0.5,
            quality_level=ResearchSourceQualityLevel.MEDIUM,
        )
        return self.returned


@pytest.mark.parametrize("origin", ["web", "local"])
def test_routes_by_explicit_origin(origin: str) -> None:
    web = RecordingEvaluator("web-quality")
    local = RecordingEvaluator("local-quality")
    router = RoutingResearchSourceQualityEvaluator(
        web_evaluator=web,
        local_evaluator=local,
    )
    source = make_document(origin)

    result = router.evaluate(source)

    selected = web if origin == "web" else local
    other = local if origin == "web" else web
    assert selected.calls == [source]
    assert other.calls == []
    assert result is selected.returned


@pytest.mark.parametrize("origin", [None, "archive"])
def test_rejects_missing_or_unknown_origin(origin: str | None) -> None:
    router = RoutingResearchSourceQualityEvaluator(
        web_evaluator=RecordingEvaluator("web-quality"),
        local_evaluator=RecordingEvaluator("local-quality"),
    )

    with pytest.raises(ValueError, match="research_origin"):
        router.evaluate(make_document(origin))
