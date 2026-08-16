"""Path-neutral normalized output from parsing one local document."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
)


class ParsedLocalDocument(BaseModel):
    """Reusable content-derived local document representation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    content: str
    content_type: ResearchSourceContentType
    sections: list[ResearchSourceDocumentSection] = Field(default_factory=list)
    format_metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parsed_document(self) -> Self:
        """Validate content, section provenance, and stable metadata."""

        if not self.content.strip():
            raise ValueError("parsed local document content must not be blank")

        section_ids = [
            section.section_id.strip().casefold() for section in self.sections
        ]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("parsed local document section IDs must be unique")

        orders = [section.order for section in self.sections]
        if len(set(orders)) != len(orders):
            raise ValueError("parsed local document section orders must be unique")
        if orders != sorted(orders):
            raise ValueError("parsed local document sections must be ordered")

        for section in self.sections:
            if section.end_character > len(self.content):
                raise ValueError("parsed local document section is outside content")
            if (
                self.content[section.start_character : section.end_character]
                != section.content
            ):
                raise ValueError("parsed local document section must match its range")

        for key, value in self.format_metadata.items():
            if not key.strip():
                raise ValueError("format metadata keys must not be blank")
            if not value.strip():
                raise ValueError("format metadata values must not be blank")

        return self
