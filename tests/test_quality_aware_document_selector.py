"""Tests for topic-relevant and diverse document selection."""

from app.research.quality_aware_document_selector import (
    QualityAwareDocumentSelector,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)
from app.schemas.research_task import ResearchTask, ResearchTaskGraph


def query_set() -> ResearchSearchQuerySet:
    graph = ResearchTaskGraph(
        request_id="request-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="request-001",
                title="Responses API",
                question="OpenAI Responses API official documentation overview",
                objective="Explain the Responses API.",
                completion_criteria=["Find relevant sources."],
                expected_output="Supported findings.",
            )
        ],
    )
    return ResearchSearchQuerySet(
        request_id="request-001",
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-001",
                request_id="request-001",
                task_id="task-001",
                query_text=(
                    "OpenAI Responses API official documentation overview"
                ),
            )
        ],
    )


def document(
    *,
    source_id: str,
    title: str,
    url: str,
    content: str,
    quality: float = 0.88,
    rank: int = 1,
) -> ResearchSourceDocument:
    candidate = ResearchSourceCandidate(
        source_id=source_id,
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title=title,
        url=url,
        source_type=ResearchSourceType.OTHER,
        snippet=title,
        rank=rank,
        metadata={
            "quality": str(quality),
            "provider_score": "0.8",
        },
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
            recency_score=0.5,
            completeness_score=0.8,
            traceability_score=1.0,
            overall_score=score,
            quality_level=(
                ResearchSourceQualityEvaluation.level_for_score(score)
            ),
        )


def test_selector_prefers_specific_responses_page() -> None:
    documents = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[
            document(
                source_id="generic",
                title="API Overview",
                url="https://developers.openai.com/api/reference/overview",
                content="General API authentication and administration.",
                rank=1,
            ),
            document(
                source_id="responses",
                title="Responses Overview | OpenAI API Reference",
                url=(
                    "https://developers.openai.com/api/reference/"
                    "responses/overview"
                ),
                content=(
                    "The Responses API supports stateful interactions, "
                    "built-in tools, text and image inputs, and function calling."
                ),
                rank=2,
            ),
        ],
    )

    result = QualityAwareDocumentSelector(
        maximum_documents=1
    ).select(
        document_set=documents,
        evaluator=Evaluator(),
        query_set=query_set(),
    )

    assert result.document_set.documents[0].candidate.source_id == "responses"


def test_selector_rejects_sources_below_quality_floor() -> None:
    documents = ResearchSourceDocumentSet(
        request_id="request-001",
        documents=[
            document(
                source_id="official",
                title="Responses API overview",
                url="https://developers.openai.com/responses",
                content="Official Responses API description.",
                quality=0.88,
                rank=1,
            ),
            document(
                source_id="blog",
                title="Responses API overview",
                url="https://example.net/blog/responses",
                content="Secondary Responses API article.",
                quality=0.66,
                rank=2,
            ),
        ],
    )

    result = QualityAwareDocumentSelector(
        maximum_documents=2,
        maximum_quality_gap=0.12,
    ).select(
        document_set=documents,
        evaluator=Evaluator(),
        query_set=query_set(),
    )

    assert [
        item.candidate.source_id
        for item in result.document_set.documents
    ] == ["official"]
