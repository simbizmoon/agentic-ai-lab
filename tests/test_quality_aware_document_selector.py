"""Tests for quality-aware live document selection."""

from app.research.quality_aware_document_selector import (
    QualityAwareDocumentSelector,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)


def document(
    *,
    source_id: str,
    rank: int,
    score: str,
) -> ResearchSourceDocument:
    content = f"Content for {source_id}."
    candidate = ResearchSourceCandidate(
        source_id=source_id,
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title=source_id,
        url=f"https://example.com/{source_id}",
        source_type=ResearchSourceType.OTHER,
        rank=rank,
        metadata={"quality": score},
    )
    return ResearchSourceDocument(
        document_id=f"document-{source_id}",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
    )


class Evaluator:
    def evaluate(
        self,
        value: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        score = float(value.candidate.metadata["quality"])
        return ResearchSourceQualityEvaluation(
            document=value,
            evaluator="test",
            authority_score=score,
            primary_source_score=score,
            recency_score=score,
            completeness_score=score,
            traceability_score=1.0,
            overall_score=score,
            quality_level=(
                ResearchSourceQualityEvaluation
                .level_for_score(score)
            ),
        )


def test_selector_keeps_highest_quality_documents() -> None:
    documents = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[
            document(source_id="low", rank=1, score="0.4"),
            document(source_id="high", rank=3, score="0.9"),
            document(source_id="medium", rank=2, score="0.7"),
        ],
    )

    result = QualityAwareDocumentSelector(
        maximum_documents=2
    ).select(
        document_set=documents,
        evaluator=Evaluator(),
    )

    assert [
        item.candidate.source_id
        for item in result.document_set.documents
    ] == ["high", "medium"]
    assert [
        item.overall_score
        for item in result.evaluations
    ] == [0.9, 0.7]
