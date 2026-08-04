"""Tests for the research evidence extractor contract."""

import pytest

from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.research.research_evidence_extractor_validator import (
    ResearchEvidenceExtractorValidator,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
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
    ResearchSourceDocumentStatus,
)

CONTENT = "Agent memory stores contextual information."


def candidate() -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id="source-001",
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def document(
    *,
    document_id: str = "document-001",
) -> ResearchSourceDocument:
    """Return one valid source document."""

    return ResearchSourceDocument(
        document_id=document_id,
        candidate=candidate(),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="stub-reader",
    )


class StubEvidenceExtractor(
    ResearchEvidenceExtractor
):
    """Simple extractor implementation for contract tests."""

    def __init__(
        self,
        *,
        name: str = "stub-extractor",
    ) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Return the extractor name."""

        return self._name

    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        """Return one deterministic evidence item."""

        source = document.candidate

        evidence = ResearchEvidence(
            evidence_id="evidence-001",
            request_id=source.request_id,
            task_id=source.task_id,
            source_id=source.source_id,
            document_id=document.document_id,
            excerpt=document.content,
            start_character=0,
            end_character=len(document.content),
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=1.0,
            confidence_score=1.0,
        )

        return ResearchEvidenceExtractionResult(
            document=document,
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
            ),
            extractor=self.name,
            evidence=[evidence],
            duration_ms=0,
        )


def test_extractor_implements_contract() -> None:
    extractor = StubEvidenceExtractor()
    source_document = document()

    result = extractor.extract(source_document)

    assert extractor.name == "stub-extractor"
    assert result.document == source_document
    assert result.extractor == extractor.name
    assert len(result.evidence) == 1


def test_validator_accepts_valid_result() -> None:
    extractor = StubEvidenceExtractor()
    source_document = document()
    result = extractor.extract(source_document)

    validator = ResearchEvidenceExtractorValidator()

    validator.validate_extractor(extractor)
    validator.validate_result(
        extractor=extractor,
        document=source_document,
        result=result,
    )


def test_validator_rejects_blank_name() -> None:
    extractor = StubEvidenceExtractor(name=" ")

    with pytest.raises(
        ValueError,
        match=(
            "evidence extractor name must not be blank"
        ),
    ):
        (
            ResearchEvidenceExtractorValidator()
            .validate_extractor(extractor)
        )


def test_validator_rejects_different_document() -> None:
    extractor = StubEvidenceExtractor()
    original = document(document_id="document-001")
    different = document(document_id="document-002")
    result = extractor.extract(different)

    with pytest.raises(
        ValueError,
        match=(
            "extraction result document must match "
            "the extractor input document"
        ),
    ):
        (
            ResearchEvidenceExtractorValidator()
            .validate_result(
                extractor=extractor,
                document=original,
                result=result,
            )
        )


def test_validator_rejects_extractor_name_mismatch() -> None:
    extractor = StubEvidenceExtractor()
    source_document = document()
    source = source_document.candidate

    evidence = ResearchEvidence(
        evidence_id="evidence-001",
        request_id=source.request_id,
        task_id=source.task_id,
        source_id=source.source_id,
        document_id=source_document.document_id,
        excerpt=source_document.content,
        start_character=0,
        end_character=len(source_document.content),
        evidence_type=ResearchEvidenceType.FACT,
        relevance_score=1.0,
        confidence_score=1.0,
    )

    result = ResearchEvidenceExtractionResult(
        document=source_document,
        status=(
            ResearchEvidenceExtractionStatus.SUCCEEDED
        ),
        extractor="different-extractor",
        evidence=[evidence],
        duration_ms=0,
    )

    with pytest.raises(
        ValueError,
        match=(
            "extraction result extractor must match "
            "the evidence extractor name"
        ),
    ):
        (
            ResearchEvidenceExtractorValidator()
            .validate_result(
                extractor=extractor,
                document=source_document,
                result=result,
            )
        )
