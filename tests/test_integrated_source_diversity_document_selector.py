"""Tests for Integrated Research source-universe document ranking."""

from __future__ import annotations

import pytest

from app.research.integrated_source_diversity_document_selector import (
    IntegratedSourceDiversityDocumentSelector,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import ResearchSourceQualityEvaluation


def document(
    source_id: str,
    *,
    origin: str | None,
    quality: float,
    rank: int,
) -> ResearchSourceDocument:
    metadata = {"quality": str(quality)}
    if origin is not None:
        metadata["research_origin"] = origin
    candidate = ResearchSourceCandidate(
        source_id=source_id,
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title=f"AIRA integrated evidence {source_id}",
        url=f"https://example.com/{source_id}",
        source_type=ResearchSourceType.OTHER,
        snippet="AIRA integrated Web and Local evidence.",
        rank=rank,
        metadata=metadata,
    )
    content = f"AIRA integrated evidence from {source_id}."
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
        self, value: ResearchSourceDocument
    ) -> ResearchSourceQualityEvaluation:
        score = float(value.candidate.metadata["quality"])
        return ResearchSourceQualityEvaluation(
            document=value,
            evaluator="test-quality",
            authority_score=score,
            primary_source_score=score,
            recency_score=score,
            completeness_score=score,
            traceability_score=score,
            overall_score=score,
            quality_level=ResearchSourceQualityEvaluation.level_for_score(score),
        )


def selection(documents: list[ResearchSourceDocument], *, maximum: int):
    return IntegratedSourceDiversityDocumentSelector(maximum_documents=maximum).rank(
        document_set=ResearchSourceDocumentSet(
            request_id="request-001", documents=documents
        ),
        evaluator=Evaluator(),
    )


def test_reserves_best_web_and_local_before_combined_quality_order() -> None:
    result = selection(
        [
            document("web-best", origin="web", quality=0.98, rank=1),
            document("web-next", origin="web", quality=0.94, rank=2),
            document("local-best", origin="local", quality=0.50, rank=3),
            document("local-low", origin="local", quality=0.20, rank=4),
        ],
        maximum=4,
    )

    assert [item.candidate.source_id for item in result.document_set.documents] == [
        "web-best",
        "local-best",
        "web-next",
    ]


def test_maximum_one_uses_existing_combined_quality_order() -> None:
    result = selection(
        [
            document("local", origin="local", quality=0.60, rank=1),
            document("web", origin="web", quality=0.95, rank=2),
        ],
        maximum=1,
    )

    assert result.document_set.documents[0].candidate.source_id == "web"


@pytest.mark.parametrize("origin", ["web", "local"])
def test_one_sided_documents_keep_quality_order(origin: str) -> None:
    result = selection(
        [
            document("lower", origin=origin, quality=0.85, rank=1),
            document("higher", origin=origin, quality=0.95, rank=2),
        ],
        maximum=2,
    )

    assert [item.candidate.source_id for item in result.document_set.documents] == [
        "higher",
        "lower",
    ]


@pytest.mark.parametrize("origin", [None, "archive"])
def test_missing_or_unknown_origin_fails_explicitly(origin: str | None) -> None:
    with pytest.raises(ValueError, match="research_origin"):
        selection(
            [document("invalid", origin=origin, quality=0.9, rank=1)],
            maximum=2,
        )


def test_select_never_exceeds_maximum_documents() -> None:
    documents = [
        document("web-1", origin="web", quality=0.98, rank=1),
        document("web-2", origin="web", quality=0.96, rank=2),
        document("local-1", origin="local", quality=0.80, rank=3),
    ]
    result = IntegratedSourceDiversityDocumentSelector(maximum_documents=2).select(
        document_set=ResearchSourceDocumentSet(
            request_id="request-001", documents=documents
        ),
        evaluator=Evaluator(),
    )

    assert [item.candidate.source_id for item in result.document_set.documents] == [
        "web-1",
        "local-1",
    ]
