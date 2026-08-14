"""Schemas for documents stored by an in-memory source reader."""

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
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)


class InMemoryResearchDocumentReadMode(StrEnum):
    """Configured behavior for one in-memory document."""

    READABLE = "readable"
    FAIL = "fail"


class InMemoryResearchDocumentRecord(BaseModel):
    """One source document stored by the in-memory reader."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    url: str
    content_type: ResearchSourceContentType = (
        ResearchSourceContentType.TEXT
    )
    content: str = ""
    sections: list[ResearchSourceDocumentSection] = Field(
        default_factory=list
    )
    language: str | None = None
    read_mode: InMemoryResearchDocumentReadMode = (
        InMemoryResearchDocumentReadMode.READABLE
    )
    failure_type: str | None = None
    failure_message: str | None = None
    retryable: bool = False
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate readable and failing record states."""

        if not self.source_id.strip():
            raise ValueError(
                "source_id must not be blank"
            )

        if not self.url.strip():
            raise ValueError(
                "url must not be blank"
            )

        if self.language is not None and not self.language.strip():
            raise ValueError(
                "language must not be blank when provided"
            )

        if (
            self.read_mode
            is InMemoryResearchDocumentReadMode.READABLE
        ):
            if not self.content.strip():
                raise ValueError(
                    "readable record content must not be blank"
                )

            if self.failure_type is not None:
                raise ValueError(
                    "readable record must not contain "
                    "failure_type"
                )

            if self.failure_message is not None:
                raise ValueError(
                    "readable record must not contain "
                    "failure_message"
                )

            self._validate_sections()

        elif (
            self.read_mode
            is InMemoryResearchDocumentReadMode.FAIL
        ):
            if self.content:
                raise ValueError(
                    "failing record must not contain content"
                )

            if self.sections:
                raise ValueError(
                    "failing record must not contain sections"
                )

            if (
                self.failure_type is None
                or not self.failure_type.strip()
            ):
                raise ValueError(
                    "failing record must contain failure_type"
                )

            if (
                self.failure_message is None
                or not self.failure_message.strip()
            ):
                raise ValueError(
                    "failing record must contain "
                    "failure_message"
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

    def _validate_sections(self) -> None:
        """Validate optional prebuilt sections against record content."""

        section_ids = [
            section.section_id.strip().casefold()
            for section in self.sections
        ]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError(
                "record section IDs must be unique"
            )

        orders = [section.order for section in self.sections]
        if len(set(orders)) != len(orders):
            raise ValueError(
                "record section orders must be unique"
            )
        if orders != sorted(orders):
            raise ValueError(
                "record sections must be ordered by order"
            )

        for section in self.sections:
            if section.end_character > len(self.content):
                raise ValueError(
                    "record section range must be within content"
                )
            if self.content[
                section.start_character:section.end_character
            ] != section.content:
                raise ValueError(
                    "record section content must match its range"
                )
