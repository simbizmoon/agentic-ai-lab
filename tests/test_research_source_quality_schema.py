"""Tests for research source quality schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

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
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
    ResearchSourceQualityLevel,
)

CONTENT = "Agent memory research content."


def document(
    *,
    status: ResearchSourceDocumentStatus = (
        ResearchSourceDocumentStatus.READ
    ),
) -> ResearchSourceDocument:
    """Return one source document."""

    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        author="Example Author",
        publisher="Example Publisher",
        published_at=date(2026, 1, 1),
        rank=1,
    )

    if status is ResearchSourceDocumentStatus.FAILED:
        return ResearchSourceDocument(
            document_id="document-001",
            candidate=candidate,
            status=status,
            content_type=ResearchSourceContentType.OTHER,
            reader="test-reader",
            error=ResearchSourceDocumentError(
                error_type="ReadFailure",
                message="Read failed.",
            ),
        )

    return ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=status,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )


def evaluation(
    **overrides: object,
) -> ResearchSourceQualityEvaluation:
    """Return one valid quality evaluation."""

    values: dict[str, object] = {
        "document": document(),
        "evaluator": "test-evaluator",
        "authority_score": 0.9,
        "primary_source_score": 0.8,
        "recency_score": 1.0,
        "completeness_score": 0.45,
        "traceability_score": 1.0,
        "overall_score": 0.77,
        "quality_level": (
            ResearchSourceQualityLevel.HIGH
        ),
        "strengths": [
            "High-authority source type",
        ],
        "limitations": [
            "Document content is limited",
        ],
        "metadata": {
            "method": "test",
        },
    }
    values.update(overrides)

    return ResearchSourceQualityEvaluation.model_validate(
        values
    )


def test_evaluation_accepts_valid_values() -> None:
    value = evaluation()

    assert value.quality_level is (
        ResearchSourceQualityLevel.HIGH
    )
    assert value.overall_score == 0.77


def test_evaluation_rejects_failed_document() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "source quality evaluation requires "
            "a successfully read document"
        ),
    ):
        evaluation(
            document=document(
                status=ResearchSourceDocumentStatus.FAILED
            )
        )


def test_evaluation_rejects_blank_evaluator() -> None:
    with pytest.raises(
        ValidationError,
        match="evaluator must not be blank",
    ):
        evaluation(evaluator=" ")


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("authority_score", -0.1),
        ("primary_source_score", 1.1),
        ("recency_score", -0.1),
        ("completeness_score", 1.1),
        ("traceability_score", -0.1),
        ("overall_score", 1.1),
    ],
)
def test_evaluation_rejects_invalid_scores(
    field_name: str,
    field_value: float,
) -> None:
    with pytest.raises(ValidationError):
        evaluation(
            **{field_name: field_value}
        )


def test_evaluation_rejects_wrong_quality_level() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "quality_level must match overall_score"
        ),
    ):
        evaluation(
            overall_score=0.9,
            quality_level=ResearchSourceQualityLevel.LOW,
        )


def test_evaluation_rejects_blank_strength() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "strengths must not contain blank values"
        ),
    ):
        evaluation(strengths=[" "])


def test_evaluation_rejects_duplicate_limitations() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "limitations must not contain duplicates"
        ),
    ):
        evaluation(
            limitations=[
                "Missing metadata",
                " missing metadata ",
            ]
        )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.90, ResearchSourceQualityLevel.EXCELLENT),
        (0.85, ResearchSourceQualityLevel.EXCELLENT),
        (0.84, ResearchSourceQualityLevel.HIGH),
        (0.70, ResearchSourceQualityLevel.HIGH),
        (0.69, ResearchSourceQualityLevel.MEDIUM),
        (0.45, ResearchSourceQualityLevel.MEDIUM),
        (0.44, ResearchSourceQualityLevel.LOW),
    ],
)
def test_level_for_score(
    score: float,
    expected: ResearchSourceQualityLevel,
) -> None:
    assert (
        ResearchSourceQualityEvaluation.level_for_score(
            score
        )
        is expected
    )
