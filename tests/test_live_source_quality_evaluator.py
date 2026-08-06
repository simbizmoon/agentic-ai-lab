"""Tests for live web source quality evaluation."""

from app.research.live_source_quality_evaluator import (
    LiveWebSourceQualityEvaluator,
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


def document(
    *,
    url: str,
    source_type: ResearchSourceType = ResearchSourceType.OTHER,
) -> ResearchSourceDocument:
    content = "Authoritative source content. " * 80
    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title="Source",
        url=url,
        source_type=source_type,
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


def test_docs_host_scores_above_generic_blog() -> None:
    evaluator = LiveWebSourceQualityEvaluator()

    docs = evaluator.evaluate(
        document(url="https://developers.example.com/docs")
    )
    blog = evaluator.evaluate(
        document(url="https://blog.example.net/post")
    )

    assert docs.authority_score > blog.authority_score
    assert docs.primary_source_score > blog.primary_source_score
    assert docs.overall_score > blog.overall_score


def test_declared_official_documentation_is_excellent() -> None:
    result = LiveWebSourceQualityEvaluator().evaluate(
        document(
            url="https://example.com/reference",
            source_type=(
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            ),
        )
    )

    assert result.authority_score == 0.95
    assert result.primary_source_score == 0.95
    assert result.quality_level.value == "excellent"
