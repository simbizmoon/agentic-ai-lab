"""Tests for research evidence extraction result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionError,
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
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

CONTENT = (
    "Agent memory stores contextual information.\n\n"
    "Episodic memory records prior experiences."
)
FIRST_PARAGRAPH = (
    "Agent memory stores contextual information."
)


def candidate(
    *,
    request_id: str = "research-001",
    task_id: str = "task-001",
    source_id: str = "source-001",
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id=request_id,
        task_id=task_id,
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def document() -> ResearchSourceDocument:
    """Return one successfully read document."""

    return ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate(),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[
            ResearchSourceDocumentSection(
                section_id="section-001",
                content=FIRST_PARAGRAPH,
                order=1,
                start_character=0,
                end_character=len(FIRST_PARAGRAPH),
            )
        ],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="in-memory-reader",
    )


def failed_document() -> ResearchSourceDocument:
    """Return one failed source document."""

    return ResearchSourceDocument(
        document_id="document-failed",
        candidate=candidate(),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="in-memory-reader",
        error=ResearchSourceDocumentError(
            error_type="ReadFailure",
            message="The document could not be read.",
        ),
    )


def evidence(
    **overrides: object,
) -> ResearchEvidence:
    """Return one valid evidence item."""

    values: dict[str, object] = {
        "evidence_id": "evidence-001",
        "request_id": "research-001",
        "task_id": "task-001",
        "source_id": "source-001",
        "document_id": "document-001",
        "section_id": "section-001",
        "excerpt": FIRST_PARAGRAPH,
        "start_character": 0,
        "end_character": len(FIRST_PARAGRAPH),
        "evidence_type": ResearchEvidenceType.FACT,
        "stance": ResearchEvidenceStance.SUPPORTS,
        "relevance_score": 0.9,
        "confidence_score": 0.8,
    }
    values.update(overrides)

    return ResearchEvidence.model_validate(values)


def extraction_error() -> ResearchEvidenceExtractionError:
    """Return one valid extraction error."""

    return ResearchEvidenceExtractionError(
        error_type="ExtractionFailure",
        message="Evidence extraction failed.",
        retryable=True,
    )


def test_succeeded_result_accepts_evidence() -> None:
    result = ResearchEvidenceExtractionResult(
        document=document(),
        status=(
            ResearchEvidenceExtractionStatus.SUCCEEDED
        ),
        extractor="stub-extractor",
        evidence=[evidence()],
        duration_ms=4,
    )

    assert len(result.evidence) == 1
    assert result.error is None


def test_no_evidence_result_accepts_empty_evidence() -> None:
    result = ResearchEvidenceExtractionResult(
        document=document(),
        status=(
            ResearchEvidenceExtractionStatus.NO_EVIDENCE
        ),
        extractor="stub-extractor",
        evidence=[],
        duration_ms=2,
    )

    assert result.evidence == []
    assert result.error is None


def test_failed_result_accepts_structured_error() -> None:
    result = ResearchEvidenceExtractionResult(
        document=document(),
        status=ResearchEvidenceExtractionStatus.FAILED,
        extractor="stub-extractor",
        evidence=[],
        error=extraction_error(),
        duration_ms=1,
    )

    assert result.error is not None
    assert result.error.retryable is True


def test_result_rejects_failed_source_document() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence extraction requires "
            "a successfully read document"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=failed_document(),
            status=(
                ResearchEvidenceExtractionStatus.NO_EVIDENCE
            ),
            extractor="stub-extractor",
            duration_ms=1,
        )


def test_succeeded_result_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "succeeded extraction must contain "
            "at least one evidence item"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[],
            duration_ms=1,
        )


def test_succeeded_result_rejects_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "succeeded extraction must not contain an error"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[evidence()],
            error=extraction_error(),
            duration_ms=1,
        )


def test_no_evidence_result_rejects_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "no-evidence extraction must not "
            "contain evidence"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.NO_EVIDENCE
            ),
            extractor="stub-extractor",
            evidence=[evidence()],
            duration_ms=1,
        )


def test_failed_result_requires_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed extraction must contain an error"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.FAILED
            ),
            extractor="stub-extractor",
            evidence=[],
            duration_ms=1,
        )


def test_failed_result_rejects_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed extraction must not contain evidence"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.FAILED
            ),
            extractor="stub-extractor",
            evidence=[evidence()],
            error=extraction_error(),
            duration_ms=1,
        )


def test_result_rejects_request_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence request_id must match "
            "the document request_id"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(request_id="research-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_task_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence task_id must match "
            "the document task_id"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(task_id="task-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_source_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence source_id must match "
            "the document source_id"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(source_id="source-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_document_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence document_id must match "
            "the input document_id"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(document_id="document-002")
            ],
            duration_ms=1,
        )


def test_result_rejects_excerpt_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence excerpt must match "
            "the document character range"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(
                    excerpt="Wrong",
                    start_character=0,
                    end_character=5,
                )
            ],
            duration_ms=1,
        )


def test_result_rejects_missing_section() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence section_id must reference "
            "an existing document section"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(section_id="missing-section")
            ],
            duration_ms=1,
        )


def test_result_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "extracted evidence IDs must be unique"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(
                    evidence_id="evidence-001"
                ),
                evidence(
                    evidence_id=" EVIDENCE-001 ",
                    section_id=None,
                    excerpt="Episodic memory",
                    start_character=CONTENT.index(
                        "Episodic memory"
                    ),
                    end_character=(
                        CONTENT.index("Episodic memory")
                        + len("Episodic memory")
                    ),
                ),
            ],
            duration_ms=1,
        )


def test_result_rejects_duplicate_ranges() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "extracted evidence ranges must be unique"
        ),
    ):
        ResearchEvidenceExtractionResult(
            document=document(),
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor="stub-extractor",
            evidence=[
                evidence(
                    evidence_id="evidence-001"
                ),
                evidence(
                    evidence_id="evidence-002"
                ),
            ],
            duration_ms=1,
        )


def test_result_orders_evidence_by_range() -> None:
    second_excerpt = "Episodic memory"
    second_start = CONTENT.index(second_excerpt)

    result = ResearchEvidenceExtractionResult(
        document=document(),
        status=(
            ResearchEvidenceExtractionStatus.SUCCEEDED
        ),
        extractor="stub-extractor",
        evidence=[
            evidence(
                evidence_id="evidence-002",
                section_id=None,
                excerpt=second_excerpt,
                start_character=second_start,
                end_character=(
                    second_start + len(second_excerpt)
                ),
            ),
            evidence(
                evidence_id="evidence-001",
            ),
        ],
        duration_ms=1,
    )

    assert [
        item.evidence_id
        for item in result.ordered_evidence()
    ] == [
        "evidence-001",
        "evidence-002",
    ]


def test_extraction_error_rejects_blank_values() -> None:
    with pytest.raises(
        ValidationError,
        match="error_type must not be blank",
    ):
        ResearchEvidenceExtractionError(
            error_type=" ",
            message="Failure.",
        )

    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        ResearchEvidenceExtractionError(
            error_type="Failure",
            message=" ",
        )
