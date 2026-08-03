"""Schemas for document Chunk embeddings."""

from __future__ import annotations

import math
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.document_chunk import DocumentChunk


class TextEmbedding(BaseModel):
    """A numeric vector representation of text."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    model_name: str = Field(min_length=1)
    dimensions: int = Field(gt=0)
    vector: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_vector(self) -> TextEmbedding:
        """Validate embedding dimensions and numeric values."""

        if len(self.vector) != self.dimensions:
            raise ValueError(
                "embedding vector length must match dimensions"
            )

        if not all(math.isfinite(value) for value in self.vector):
            raise ValueError(
                "embedding vector values must be finite"
            )

        return self


class EmbeddedDocumentChunk(BaseModel):
    """A document Chunk with its searchable embedding."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    chunk: DocumentChunk
    embedding: TextEmbedding
    metadata: dict[str, Any] = Field(default_factory=dict)
