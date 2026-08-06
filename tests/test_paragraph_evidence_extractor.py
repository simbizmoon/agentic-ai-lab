"""Tests for paragraph-based live evidence extraction."""

from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


def document(content: str) -> ResearchSourceDocument:
    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title="Responses API official overview",
        url="https://developers.example.com/responses",
        source_type=ResearchSourceType.OTHER,
        snippet="Responses API tools and stateful interactions",
        rank=1,
    )
    return ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
    )


def test_extractor_returns_bounded_traceable_chunks() -> None:
    content = (
        "Navigation words and short labels.\n\n"
        "The Responses API supports stateful interactions "
        "and built-in tools such as web search and file "
        "search. It is designed for agent workflows.\n\n"
        "A second paragraph explains response objects and "
        "how previous response identifiers preserve state. "
        "This paragraph is also directly relevant.\n\n"
        "import requests API_KEY = 'your-api-key-here' "
        "Authorization: Bearer placeholder requests.post()"
    )
    source = document(content)
    result = ParagraphEvidenceExtractor(
        maximum_evidence=2,
        minimum_characters=50,
    ).extract(source)

    assert len(result.evidence) == 2

    for evidence in result.evidence:
        assert evidence.excerpt == content[
            evidence.start_character:
            evidence.end_character
        ]
        assert len(evidence.excerpt) <= 1_200

    assert all(
        "your-api-key-here" not in evidence.excerpt
        for evidence in result.evidence
    )


def test_extractor_splits_long_paragraphs() -> None:
    content = " ".join(["evidence"] * 500)
    result = ParagraphEvidenceExtractor(
        maximum_evidence=3,
        maximum_characters=300,
        minimum_characters=50,
    ).extract(document(content))

    assert len(result.evidence) == 3
    assert all(
        len(item.excerpt) <= 300
        for item in result.evidence
    )
