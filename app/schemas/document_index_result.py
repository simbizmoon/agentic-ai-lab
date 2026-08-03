"""Schemas for document indexing results."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class DocumentIndexResult(BaseModel):
    """Summary of a completed document indexing operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    document_id: str = Field(min_length=1)
    chunk_count: int = Field(ge=0)
    embedding_model: str = Field(min_length=1)
    embedding_dimensions: int = Field(gt=0)
