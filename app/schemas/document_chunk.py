"""Schemas for document chunks used in retrieval workflows."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class DocumentChunk(BaseModel):
    """A searchable portion of a source document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_character_range(self) -> DocumentChunk:
        """Ensure the character range matches the Chunk text."""

        if self.end_char <= self.start_char:
            raise ValueError(
                "end_char must be greater than start_char"
            )

        if len(self.text) != self.end_char - self.start_char:
            raise ValueError(
                "Chunk text length must match character range"
            )

        return self
