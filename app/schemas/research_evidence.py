"""Schemas for evidence extracted from research source documents."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


class ResearchEvidenceType(StrEnum):
    """Semantic type of one extracted evidence item."""

    FACT = "fact"
    DEFINITION = "definition"
    STATISTIC = "statistic"
    EXAMPLE = "example"
    METHOD = "method"
    OPINION = "opinion"
    LIMITATION = "limitation"
    CONTRADICTION = "contradiction"
    OTHER = "other"


class ResearchEvidenceStance(StrEnum):
    """Relationship between evidence and a proposed claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class ResearchEvidence(BaseModel):
    """One traceable evidence excerpt from a source document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    request_id: str
    task_id: str
    source_id: str
    document_id: str
    section_id: str | None = None
    excerpt: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=1)
    evidence_type: ResearchEvidenceType
    stance: ResearchEvidenceStance = (
        ResearchEvidenceStance.NEUTRAL
    )
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    rationale: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate evidence identity, excerpt, and scores."""

        required_text = {
            "evidence_id": self.evidence_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "excerpt": self.excerpt,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if (
            self.section_id is not None
            and not self.section_id.strip()
        ):
            raise ValueError(
                "section_id must not be blank when provided"
            )

        if self.end_character <= self.start_character:
            raise ValueError(
                "end_character must be greater than "
                "start_character"
            )

        if (
            self.rationale is not None
            and not self.rationale.strip()
        ):
            raise ValueError(
                "rationale must not be blank when provided"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class ResearchEvidenceSet(BaseModel):
    """Validated evidence collection linked to source documents."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    document_set: ResearchSourceDocumentSet
    evidence: list[ResearchEvidence] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_evidence_set(self) -> Self:
        """Validate evidence against its source documents."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        if self.document_set.request_id != self.request_id:
            raise ValueError(
                "document set request_id must match "
                "evidence set request_id"
            )

        evidence_ids = [
            item.evidence_id.strip().casefold()
            for item in self.evidence
        ]

        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "evidence IDs must be unique"
            )

        document_by_id = {
            document.document_id.strip().casefold(): document
            for document in self.document_set.documents
        }

        range_keys: list[tuple[str, int, int]] = []

        for item in self.evidence:
            if item.request_id != self.request_id:
                raise ValueError(
                    "all evidence request IDs must match "
                    "the evidence set request_id"
                )

            document = document_by_id.get(
                item.document_id.strip().casefold()
            )

            if document is None:
                raise ValueError(
                    "all evidence must reference "
                    "existing documents"
                )

            self._validate_document_reference(
                evidence=item,
                document=document,
            )

            range_keys.append(
                (
                    item.document_id.strip().casefold(),
                    item.start_character,
                    item.end_character,
                )
            )

        if len(set(range_keys)) != len(range_keys):
            raise ValueError(
                "evidence document ranges must be unique"
            )

        return self

    @staticmethod
    def _validate_document_reference(
        *,
        evidence: ResearchEvidence,
        document: ResearchSourceDocument,
    ) -> None:
        """Validate one evidence item against one document."""

        if (
            document.status
            is not ResearchSourceDocumentStatus.READ
        ):
            raise ValueError(
                "evidence cannot reference "
                "a failed document"
            )

        candidate = document.candidate

        if evidence.task_id != candidate.task_id:
            raise ValueError(
                "evidence task_id must match "
                "the document task_id"
            )

        if evidence.source_id != candidate.source_id:
            raise ValueError(
                "evidence source_id must match "
                "the document source_id"
            )

        if evidence.end_character > len(document.content):
            raise ValueError(
                "evidence character range must be "
                "within document content"
            )

        expected_excerpt = document.content[
            evidence.start_character:
            evidence.end_character
        ]

        if expected_excerpt != evidence.excerpt:
            raise ValueError(
                "evidence excerpt must match "
                "the document character range"
            )

        if evidence.section_id is not None:
            section = next(
                (
                    item
                    for item in document.sections
                    if item.section_id.strip().casefold()
                    == evidence.section_id.strip().casefold()
                ),
                None,
            )

            if section is None:
                raise ValueError(
                    "evidence section_id must reference "
                    "an existing document section"
                )

            if (
                evidence.start_character
                < section.start_character
                or evidence.end_character
                > section.end_character
            ):
                raise ValueError(
                    "evidence range must be within "
                    "the referenced section"
                )

    def ordered_evidence(
        self,
    ) -> list[ResearchEvidence]:
        """Return evidence in deterministic document order."""

        document_positions = {
            document.document_id.strip().casefold(): position
            for position, document in enumerate(
                self.document_set.documents
            )
        }

        original_positions = {
            item.evidence_id: position
            for position, item in enumerate(self.evidence)
        }

        return sorted(
            self.evidence,
            key=lambda item: (
                document_positions[
                    item.document_id.strip().casefold()
                ],
                item.start_character,
                item.end_character,
                original_positions[item.evidence_id],
            ),
        )

    def evidence_for_task(
        self,
        task_id: str,
    ) -> list[ResearchEvidence]:
        """Return ordered evidence belonging to one task."""

        if not task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        normalized_task_id = task_id.strip().casefold()

        return [
            item
            for item in self.ordered_evidence()
            if item.task_id.strip().casefold()
            == normalized_task_id
        ]

    def supporting_evidence(
        self,
    ) -> list[ResearchEvidence]:
        """Return evidence classified as supporting."""

        return [
            item
            for item in self.ordered_evidence()
            if item.stance
            is ResearchEvidenceStance.SUPPORTS
        ]

    def contradicting_evidence(
        self,
    ) -> list[ResearchEvidence]:
        """Return evidence classified as contradicting."""

        return [
            item
            for item in self.ordered_evidence()
            if item.stance
            is ResearchEvidenceStance.CONTRADICTS
        ]
