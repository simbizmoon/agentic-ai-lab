"""Tests for deterministic research source quality evaluation."""

from datetime import date

import pytest

from app.research.research_source_quality_evaluator import (
    ResearchSourceQualityEvaluator,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityLevel,
)


def document(
    *,
    source_type: ResearchSourceType = (
        ResearchSourceType.PRIMARY_RESEARCH
    ),
    published_at: date | None = date(2026, 1, 1),
    author: str | None = "Example Author",
    publisher: str | None = "Example Publisher",
    content: str | None = None,
    include_sections: bool = True,
    language: str | None = "en",
) -> ResearchSourceDocument:
    """Return one successfully read source document."""

    source_content = (
        content
        if content is not None
        else "A" * 600
    )

    sections: list[
        ResearchSourceDocumentSection
    ] = []

    if include_sections:
        sections.append(
            ResearchSourceDocumentSection(
                section_id="section-001",
                content=source_content,
                order=1,
                start_character=0,
                end_character=len(source_content),
            )
        )

    return ResearchSourceDocument(
        document_id="document-001",
        candidate=ResearchSourceCandidate(
            source_id="source-001",
            request_id="research-001",
            task_id="task-001",
            query_id="query-001",
            title="Research source",
            url="https://example.com/source",
            source_type=source_type,
            author=author,
            publisher=publisher,
            published_at=published_at,
            rank=1,
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=source_content,
        language=language,
        sections=sections,
        word_count=len(source_content.split()),
        character_count=len(source_content),
        reader="test-reader",
    )


def evaluator() -> ResearchSourceQualityEvaluator:
    """Return one deterministic evaluator."""

    return ResearchSourceQualityEvaluator(
        reference_date=date(2026, 8, 4)
    )


def test_evaluator_scores_high_quality_source() -> None:
    result = evaluator().evaluate(document())

    assert result.authority_score == 0.95
    assert result.primary_source_score == 1.0
    assert result.recency_score == 1.0
    assert result.traceability_score == 1.0
    assert result.overall_score >= 0.85
    assert result.quality_level is (
        ResearchSourceQualityLevel.EXCELLENT
    )


def test_evaluator_scores_official_documentation() -> None:
    result = evaluator().evaluate(
        document(
            source_type=(
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            )
        )
    )

    assert result.authority_score == 1.0
    assert result.primary_source_score == 0.95


def test_evaluator_penalizes_missing_publication_date() -> None:
    result = evaluator().evaluate(
        document(published_at=None)
    )

    assert result.recency_score == 0.3
    assert (
        "Publication is old or undated"
        in result.limitations
    )


def test_evaluator_penalizes_old_source() -> None:
    result = evaluator().evaluate(
        document(
            published_at=date(2010, 1, 1)
        )
    )

    assert result.recency_score == 0.2


def test_evaluator_penalizes_future_date() -> None:
    result = evaluator().evaluate(
        document(
            published_at=date(2027, 1, 1)
        )
    )

    assert result.recency_score == 0.4


def test_evaluator_scores_short_unstructured_content() -> None:
    result = evaluator().evaluate(
        document(
            content="Short source content.",
            include_sections=False,
            language=None,
        )
    )

    assert result.completeness_score == 0.15
    assert (
        "Document content is limited"
        in result.limitations
    )
    assert (
        "Document has no extracted sections"
        in result.limitations
    )


def test_evaluator_scores_traceability() -> None:
    result = evaluator().evaluate(
        document(
            author=None,
            publisher=None,
            published_at=None,
        )
    )

    assert result.traceability_score == 0.25
    assert (
        "Source metadata is incomplete"
        in result.limitations
    )


def test_evaluator_rejects_failed_document() -> None:
    source = document().candidate

    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=source,
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="test-reader",
        error=ResearchSourceDocumentError(
            error_type="ReadFailure",
            message="Read failed.",
        ),
    )

    with pytest.raises(
        ValueError,
        match="cannot evaluate a failed document",
    ):
        evaluator().evaluate(failed)


def test_evaluator_rejects_blank_name() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        ResearchSourceQualityEvaluator(
            reference_date=date(2026, 8, 4),
            name=" ",
        )


def test_evaluation_is_deterministic() -> None:
    value = evaluator()
    source_document = document()

    first = value.evaluate(source_document)
    second = value.evaluate(source_document)

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
