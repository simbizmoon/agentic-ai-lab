"""Tests for research evidence schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
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
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

CONTENT = (
    "Agent memory stores contextual information.\n\n"
    "Episodic memory records prior experiences."
)
FIRST_PARAGRAPH = (
    "Agent memory stores contextual information."
)
SECOND_PARAGRAPH = (
    "Episodic memory records prior experiences."
)
SECOND_START = CONTENT.index(SECOND_PARAGRAPH)


def candidate(
    *,
    source_id: str = "source-001",
    task_id: str = "task-001",
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="research-001",
        task_id=task_id,
        query_id=f"query-{task_id}",
        title=f"Research for {task_id}",
        url=f"https://example.com/{source_id}",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def document(
    *,
    document_id: str = "document-001",
    source_id: str = "source-001",
    task_id: str = "task-001",
) -> ResearchSourceDocument:
    """Return one successfully read document."""

    return ResearchSourceDocument(
        document_id=document_id,
        candidate=candidate(
            source_id=source_id,
            task_id=task_id,
        ),
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
            ),
            ResearchSourceDocumentSection(
                section_id="section-002",
                content=SECOND_PARAGRAPH,
                order=2,
                start_character=SECOND_START,
                end_character=(
                    SECOND_START + len(SECOND_PARAGRAPH)
                ),
            ),
        ],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="in-memory-reader",
    )


def failed_document() -> ResearchSourceDocument:
    """Return one failed source document."""

    return ResearchSourceDocument(
        document_id="document-failed",
        candidate=candidate(
            source_id="source-failed",
            task_id="task-failed",
        ),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        content="",
        sections=[],
        word_count=0,
        character_count=0,
        reader="in-memory-reader",
        error=ResearchSourceDocumentError(
            error_type="ReadFailure",
            message="The document could not be read.",
        ),
    )


def document_set(
    *,
    include_failed: bool = False,
) -> ResearchSourceDocumentSet:
    """Return one valid document set."""

    documents = [document()]

    if include_failed:
        documents.append(failed_document())

    return ResearchSourceDocumentSet(
        request_id="research-001",
        documents=documents,
    )


def evidence(
    *,
    evidence_id: str = "evidence-001",
    document_id: str = "document-001",
    source_id: str = "source-001",
    task_id: str = "task-001",
    section_id: str | None = "section-001",
    excerpt: str = FIRST_PARAGRAPH,
    start_character: int = 0,
    end_character: int = len(FIRST_PARAGRAPH),
    **overrides: object,
) -> ResearchEvidence:
    """Return one valid evidence item."""

    values: dict[str, object] = {
        "evidence_id": evidence_id,
        "request_id": "research-001",
        "task_id": task_id,
        "source_id": source_id,
        "document_id": document_id,
        "section_id": section_id,
        "excerpt": excerpt,
        "start_character": start_character,
        "end_character": end_character,
        "evidence_type": ResearchEvidenceType.FACT,
        "stance": ResearchEvidenceStance.SUPPORTS,
        "relevance_score": 0.9,
        "confidence_score": 0.8,
        "rationale": (
            "The excerpt directly describes "
            "the memory function."
        ),
        "metadata": {
            "extractor": "test",
        },
    }
    values.update(overrides)

    return ResearchEvidence.model_validate(values)


def test_evidence_accepts_valid_values() -> None:
    value = evidence()

    assert value.evidence_type is ResearchEvidenceType.FACT
    assert value.stance is ResearchEvidenceStance.SUPPORTS
    assert value.relevance_score == 0.9


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("evidence_id", " "),
        ("request_id", ""),
        ("task_id", "\t"),
        ("source_id", "\n"),
        ("document_id", " "),
        ("excerpt", ""),
    ],
)
def test_evidence_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    values = evidence().model_dump()
    values[field_name] = field_value

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        ResearchEvidence.model_validate(values)


def test_evidence_rejects_blank_optional_text() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "section_id must not be blank when provided"
        ),
    ):
        evidence(section_id=" ")


def test_evidence_rejects_invalid_character_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "end_character must be greater than "
            "start_character"
        ),
    ):
        evidence(
            start_character=10,
            end_character=10,
        )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("relevance_score", -0.1),
        ("relevance_score", 1.1),
        ("confidence_score", -0.1),
        ("confidence_score", 1.1),
    ],
)
def test_evidence_rejects_invalid_scores(
    field_name: str,
    field_value: float,
) -> None:
    with pytest.raises(ValidationError):
        evidence(
            **{field_name: field_value}
        )


def test_evidence_set_accepts_matching_evidence() -> None:
    value = ResearchEvidenceSet(
        request_id="research-001",
        document_set=document_set(),
        evidence=[evidence()],
    )

    assert len(value.evidence) == 1


def test_evidence_set_allows_empty_evidence() -> None:
    value = ResearchEvidenceSet(
        request_id="research-001",
        document_set=document_set(),
        evidence=[],
    )

    assert value.evidence == []


def test_evidence_set_rejects_duplicate_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="evidence IDs must be unique",
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(evidence_id="evidence-001"),
                evidence(
                    evidence_id=" EVIDENCE-001 ",
                    section_id="section-002",
                    excerpt=SECOND_PARAGRAPH,
                    start_character=SECOND_START,
                    end_character=(
                        SECOND_START
                        + len(SECOND_PARAGRAPH)
                    ),
                ),
            ],
        )


def test_evidence_set_rejects_missing_document() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all evidence must reference "
            "existing documents"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(document_id="missing-document")
            ],
        )


def test_evidence_set_rejects_failed_document() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence cannot reference a failed document"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(
                include_failed=True
            ),
            evidence=[
                evidence(
                    document_id="document-failed",
                    source_id="source-failed",
                    task_id="task-failed",
                    section_id=None,
                    excerpt="Failure",
                    start_character=0,
                    end_character=7,
                )
            ],
        )


def test_evidence_set_rejects_task_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence task_id must match "
            "the document task_id"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(task_id="different-task")
            ],
        )


def test_evidence_set_rejects_source_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence source_id must match "
            "the document source_id"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(source_id="different-source")
            ],
        )


def test_evidence_set_rejects_range_outside_document() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence character range must be "
            "within document content"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(
                    section_id=None,
                    excerpt="Outside",
                    start_character=len(CONTENT),
                    end_character=len(CONTENT) + 7,
                )
            ],
        )


def test_evidence_set_rejects_excerpt_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence excerpt must match "
            "the document character range"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(
                    excerpt="Wrong",
                    start_character=0,
                    end_character=5,
                )
            ],
        )


def test_evidence_set_rejects_missing_section() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence section_id must reference "
            "an existing document section"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(section_id="missing-section")
            ],
        )


def test_evidence_set_rejects_range_outside_section() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence range must be within "
            "the referenced section"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(
                    section_id="section-001",
                    excerpt=SECOND_PARAGRAPH,
                    start_character=SECOND_START,
                    end_character=(
                        SECOND_START
                        + len(SECOND_PARAGRAPH)
                    ),
                )
            ],
        )


def test_evidence_set_rejects_duplicate_ranges() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "evidence document ranges must be unique"
        ),
    ):
        ResearchEvidenceSet(
            request_id="research-001",
            document_set=document_set(),
            evidence=[
                evidence(evidence_id="evidence-001"),
                evidence(evidence_id="evidence-002"),
            ],
        )


def test_evidence_set_orders_by_document_and_range() -> None:
    second_document = document(
        document_id="document-002",
        source_id="source-002",
        task_id="task-002",
    )
    documents = ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[
            document(),
            second_document,
        ],
    )

    value = ResearchEvidenceSet(
        request_id="research-001",
        document_set=documents,
        evidence=[
            evidence(
                evidence_id="evidence-003",
                document_id="document-002",
                source_id="source-002",
                task_id="task-002",
            ),
            evidence(
                evidence_id="evidence-002",
                section_id="section-002",
                excerpt=SECOND_PARAGRAPH,
                start_character=SECOND_START,
                end_character=(
                    SECOND_START + len(SECOND_PARAGRAPH)
                ),
            ),
            evidence(evidence_id="evidence-001"),
        ],
    )

    assert [
        item.evidence_id
        for item in value.ordered_evidence()
    ] == [
        "evidence-001",
        "evidence-002",
        "evidence-003",
    ]


def test_evidence_set_filters_by_task_and_stance() -> None:
    second_document = document(
        document_id="document-002",
        source_id="source-002",
        task_id="task-002",
    )
    documents = ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[
            document(),
            second_document,
        ],
    )

    value = ResearchEvidenceSet(
        request_id="research-001",
        document_set=documents,
        evidence=[
            evidence(
                evidence_id="evidence-support",
            ),
            evidence(
                evidence_id="evidence-contradict",
                document_id="document-002",
                source_id="source-002",
                task_id="task-002",
                stance=(
                    ResearchEvidenceStance.CONTRADICTS
                ),
            ),
        ],
    )

    assert [
        item.evidence_id
        for item in value.evidence_for_task(
            " TASK-002 "
        )
    ] == [
        "evidence-contradict"
    ]

    assert len(value.supporting_evidence()) == 1
    assert len(value.contradicting_evidence()) == 1


def test_evidence_set_rejects_blank_task_lookup() -> None:
    value = ResearchEvidenceSet(
        request_id="research-001",
        document_set=document_set(),
        evidence=[],
    )

    with pytest.raises(
        ValueError,
        match="task_id must not be blank",
    ):
        value.evidence_for_task(" ")
