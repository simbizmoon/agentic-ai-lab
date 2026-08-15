"""Tests for explicit-origin research source reader routing."""

from __future__ import annotations

import pytest

from app.research.research_source_reader import ResearchSourceReader
from app.research.routing_research_source_reader import RoutingResearchSourceReader
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


def candidate(origin: str | None) -> ResearchSourceCandidate:
    metadata = {} if origin is None else {"research_origin": origin}
    return ResearchSourceCandidate(
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


def document(item: ResearchSourceCandidate, reader: str) -> ResearchSourceDocument:
    content = f"Content read by {reader}."
    return ResearchSourceDocument(
        document_id=f"document-{item.source_id}",
        candidate=item,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader=reader,
    )


class RecordingReader(ResearchSourceReader):
    def __init__(self, name: str) -> None:
        self._name = name
        self.calls: list[ResearchSourceCandidate] = []
        self.returned: ResearchSourceDocument | None = None

    @property
    def name(self) -> str:
        return self._name

    def read(self, item: ResearchSourceCandidate) -> ResearchSourceDocument:
        self.calls.append(item)
        self.returned = document(item, self.name)
        return self.returned


@pytest.mark.parametrize("origin", ["web", "local"])
def test_routes_by_explicit_origin_and_preserves_document(origin: str) -> None:
    web = RecordingReader("web-reader")
    local = RecordingReader("local-reader")
    router = RoutingResearchSourceReader(web_reader=web, local_reader=local)
    item = candidate(origin)

    result = router.read(item)

    selected = web if origin == "web" else local
    other = local if origin == "web" else web
    assert selected.calls == [item]
    assert other.calls == []
    assert result is selected.returned


@pytest.mark.parametrize("origin", [None, "archive"])
def test_rejects_missing_or_unknown_origin(origin: str | None) -> None:
    router = RoutingResearchSourceReader(
        web_reader=RecordingReader("web-reader"),
        local_reader=RecordingReader("local-reader"),
    )

    with pytest.raises(ValueError, match="research_origin"):
        router.read(candidate(origin))
