"""Schemas for document retrieval results."""

from __future__ import annotations

import math

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.document_chunk import DocumentChunk


class RetrievalResult(BaseModel):
    """A retrieved document Chunk and its similarity score."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    chunk: DocumentChunk
    score: float = Field(ge=-1.0, le=1.0)
    rank: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_score(self) -> RetrievalResult:
        """Ensure the similarity score is finite."""

        if not math.isfinite(self.score):
            raise ValueError(
                "retrieval score must be finite"
            )

        return self
