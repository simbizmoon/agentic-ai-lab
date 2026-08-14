"""Schemas for research source documents and document sections."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)


class ResearchSourceDocumentStatus(StrEnum):
    """Read state of one research source document."""

    READ = "read"
    FAILED = "failed"


class ResearchSourceContentType(StrEnum):
    """Normalized content type of a source document."""

    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    PDF_TEXT = "pdf_text"
    HWPX_TEXT = "hwpx_text"
    JSON = "json"
    OTHER = "other"


class ResearchSourceDocumentSection(BaseModel):
    """One ordered section extracted from a source document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    section_id: str
    heading: str | None = None
    content: str
    order: int = Field(ge=1)
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=1)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_section(self) -> Self:
        """Validate section text and character range."""

        if not self.section_id.strip():
            raise ValueError(
                "section_id must not be blank"
            )

        if self.heading is not None and not self.heading.strip():
            raise ValueError(
                "heading must not be blank when provided"
            )

        if not self.content.strip():
            raise ValueError(
                "section content must not be blank"
            )

        if self.end_character <= self.start_character:
            raise ValueError(
                "end_character must be greater than "
                "start_character"
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


class ResearchSourceDocumentError(BaseModel):
    """Structured error raised while reading a source."""

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
        """Validate document read error details."""

        if not self.error_type.strip():
            raise ValueError(
                "error_type must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        return self


class ResearchSourceDocument(BaseModel):
    """Normalized document read from one source candidate."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    document_id: str
    candidate: ResearchSourceCandidate
    status: ResearchSourceDocumentStatus
    content_type: ResearchSourceContentType
    content: str = ""
    language: str | None = None
    sections: list[
        ResearchSourceDocumentSection
    ] = Field(default_factory=list)
    word_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)
    reader: str
    error: ResearchSourceDocumentError | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        """Validate document state and structural consistency."""

        if not self.document_id.strip():
            raise ValueError(
                "document_id must not be blank"
            )

        if not self.reader.strip():
            raise ValueError(
                "reader must not be blank"
            )

        if self.language is not None and not self.language.strip():
            raise ValueError(
                "language must not be blank when provided"
            )

        if self.status is ResearchSourceDocumentStatus.READ:
            self._validate_read_document()

        elif self.status is ResearchSourceDocumentStatus.FAILED:
            self._validate_failed_document()

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

    def _validate_read_document(self) -> None:
        """Validate a successfully read document."""

        if not self.content.strip():
            raise ValueError(
                "read document content must not be blank"
            )

        if self.error is not None:
            raise ValueError(
                "read document must not contain an error"
            )

        actual_character_count = len(self.content)

        if self.character_count != actual_character_count:
            raise ValueError(
                "character_count must match content length"
            )

        actual_word_count = len(self.content.split())

        if self.word_count != actual_word_count:
            raise ValueError(
                "word_count must match content word count"
            )

        normalized_section_ids = [
            section.section_id.strip().casefold()
            for section in self.sections
        ]

        if len(set(normalized_section_ids)) != len(
            normalized_section_ids
        ):
            raise ValueError(
                "section IDs must be unique"
            )

        orders = [
            section.order
            for section in self.sections
        ]

        if len(set(orders)) != len(orders):
            raise ValueError(
                "section orders must be unique"
            )

        for section in self.sections:
            if section.end_character > len(self.content):
                raise ValueError(
                    "section character range must be "
                    "within document content"
                )

            expected_content = self.content[
                section.start_character:
                section.end_character
            ]

            if expected_content != section.content:
                raise ValueError(
                    "section content must match "
                    "the document character range"
                )

    def _validate_failed_document(self) -> None:
        """Validate a failed document read."""

        if self.content:
            raise ValueError(
                "failed document must not contain content"
            )

        if self.sections:
            raise ValueError(
                "failed document must not contain sections"
            )

        if self.word_count != 0:
            raise ValueError(
                "failed document word_count must be zero"
            )

        if self.character_count != 0:
            raise ValueError(
                "failed document character_count "
                "must be zero"
            )

        if self.error is None:
            raise ValueError(
                "failed document must contain an error"
            )

    def ordered_sections(
        self,
    ) -> list[ResearchSourceDocumentSection]:
        """Return sections in deterministic order."""

        return sorted(
            self.sections,
            key=lambda section: section.order,
        )


class ResearchSourceDocumentSet(BaseModel):
    """Validated document collection for source candidates."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    documents: list[
        ResearchSourceDocument
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_document_set(self) -> Self:
        """Validate document identity and source uniqueness."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        normalized_document_ids = [
            document.document_id.strip().casefold()
            for document in self.documents
        ]

        if len(set(normalized_document_ids)) != len(
            normalized_document_ids
        ):
            raise ValueError(
                "document IDs must be unique"
            )

        if any(
            document.candidate.request_id
            != self.request_id
            for document in self.documents
        ):
            raise ValueError(
                "all document request IDs must match "
                "the document set request_id"
            )

        normalized_source_ids = [
            document.candidate.source_id.strip().casefold()
            for document in self.documents
        ]

        if len(set(normalized_source_ids)) != len(
            normalized_source_ids
        ):
            raise ValueError(
                "document source IDs must be unique"
            )

        return self

    def successful_documents(
        self,
    ) -> list[ResearchSourceDocument]:
        """Return successfully read documents."""

        return [
            document
            for document in self.documents
            if document.status
            is ResearchSourceDocumentStatus.READ
        ]

    def failed_documents(
        self,
    ) -> list[ResearchSourceDocument]:
        """Return failed document reads."""

        return [
            document
            for document in self.documents
            if document.status
            is ResearchSourceDocumentStatus.FAILED
        ]
