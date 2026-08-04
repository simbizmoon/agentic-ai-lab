"""Schemas for research evidence extraction execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_evidence import (
    ResearchEvidence,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


class ResearchEvidenceExtractionStatus(StrEnum):
    """Outcome of one evidence extraction execution."""

    SUCCEEDED = "succeeded"
    NO_EVIDENCE = "no_evidence"
    FAILED = "failed"


class ResearchEvidenceExtractionError(BaseModel):
    """Structured error produced during evidence extraction."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    error_type: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        """Validate extraction error details."""

        if not self.error_type.strip():
            raise ValueError(
                "error_type must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        return self


class ResearchEvidenceExtractionResult(BaseModel):
    """Result of extracting evidence from one document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    document: ResearchSourceDocument
    status: ResearchEvidenceExtractionStatus
    extractor: str
    evidence: list[ResearchEvidence] = Field(
        default_factory=list
    )
    error: ResearchEvidenceExtractionError | None = None
    duration_ms: int = Field(ge=0)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate extraction state and evidence references."""

        if not self.extractor.strip():
            raise ValueError(
                "extractor must not be blank"
            )

        if (
            self.document.status
            is not ResearchSourceDocumentStatus.READ
        ):
            raise ValueError(
                "evidence extraction requires "
                "a successfully read document"
            )

        self._validate_evidence_references()

        if (
            self.status
            is ResearchEvidenceExtractionStatus.SUCCEEDED
        ):
            if not self.evidence:
                raise ValueError(
                    "succeeded extraction must contain "
                    "at least one evidence item"
                )

            if self.error is not None:
                raise ValueError(
                    "succeeded extraction must not "
                    "contain an error"
                )

        elif (
            self.status
            is ResearchEvidenceExtractionStatus.NO_EVIDENCE
        ):
            if self.evidence:
                raise ValueError(
                    "no-evidence extraction must not "
                    "contain evidence"
                )

            if self.error is not None:
                raise ValueError(
                    "no-evidence extraction must not "
                    "contain an error"
                )

        elif (
            self.status
            is ResearchEvidenceExtractionStatus.FAILED
        ):
            if self.evidence:
                raise ValueError(
                    "failed extraction must not "
                    "contain evidence"
                )

            if self.error is None:
                raise ValueError(
                    "failed extraction must contain an error"
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

    def _validate_evidence_references(self) -> None:
        """Validate extracted evidence against the input document."""

        candidate = self.document.candidate

        normalized_ids = [
            item.evidence_id.strip().casefold()
            for item in self.evidence
        ]

        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError(
                "extracted evidence IDs must be unique"
            )

        range_keys: list[
            tuple[int, int]
        ] = []

        for item in self.evidence:
            if (
                item.request_id
                != candidate.request_id
            ):
                raise ValueError(
                    "evidence request_id must match "
                    "the document request_id"
                )

            if item.task_id != candidate.task_id:
                raise ValueError(
                    "evidence task_id must match "
                    "the document task_id"
                )

            if item.source_id != candidate.source_id:
                raise ValueError(
                    "evidence source_id must match "
                    "the document source_id"
                )

            if (
                item.document_id
                != self.document.document_id
            ):
                raise ValueError(
                    "evidence document_id must match "
                    "the input document_id"
                )

            if (
                item.end_character
                > len(self.document.content)
            ):
                raise ValueError(
                    "evidence character range must be "
                    "within document content"
                )

            expected_excerpt = self.document.content[
                item.start_character:
                item.end_character
            ]

            if expected_excerpt != item.excerpt:
                raise ValueError(
                    "evidence excerpt must match "
                    "the document character range"
                )

            if item.section_id is not None:
                section = next(
                    (
                        section
                        for section
                        in self.document.sections
                        if (
                            section.section_id
                            .strip()
                            .casefold()
                            == item.section_id
                            .strip()
                            .casefold()
                        )
                    ),
                    None,
                )

                if section is None:
                    raise ValueError(
                        "evidence section_id must reference "
                        "an existing document section"
                    )

                if (
                    item.start_character
                    < section.start_character
                    or item.end_character
                    > section.end_character
                ):
                    raise ValueError(
                        "evidence range must be within "
                        "the referenced section"
                    )

            range_keys.append(
                (
                    item.start_character,
                    item.end_character,
                )
            )

        if len(set(range_keys)) != len(range_keys):
            raise ValueError(
                "extracted evidence ranges must be unique"
            )

    def ordered_evidence(
        self,
    ) -> list[ResearchEvidence]:
        """Return evidence in deterministic document order."""

        original_positions = {
            item.evidence_id: position
            for position, item in enumerate(self.evidence)
        }

        return sorted(
            self.evidence,
            key=lambda item: (
                item.start_character,
                item.end_character,
                original_positions[item.evidence_id],
            ),
        )
