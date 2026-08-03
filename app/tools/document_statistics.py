"""Deterministic document statistics tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentStatisticsInput(BaseModel):
    """Validated input for the document statistics tool."""

    model_config = ConfigDict(extra="forbid", strict=True)

    document_text: str = Field(
        min_length=1,
        description="Document text whose statistics will be calculated.",
    )

    @field_validator("document_text")
    @classmethod
    def reject_whitespace_only_text(cls, value: str) -> str:
        """Reject text containing only whitespace."""

        if not value.strip():
            raise ValueError("document_text must contain non-whitespace text")

        return value


class DocumentStatistics(BaseModel):
    """Deterministic statistics calculated from document text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    character_count: int = Field(ge=1)
    word_count: int = Field(ge=1)
    line_count: int = Field(ge=1)


def get_document_statistics(
    tool_input: DocumentStatisticsInput,
) -> DocumentStatistics:
    """Calculate deterministic statistics for document text."""

    text = tool_input.document_text

    return DocumentStatistics(
        character_count=len(text),
        word_count=len(text.split()),
        line_count=len(text.splitlines()) or 1,
    )
