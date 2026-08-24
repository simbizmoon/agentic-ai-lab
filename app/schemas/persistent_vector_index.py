"""Implementation-neutral contracts for persistent vector-index snapshots."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_embedding import EmbeddedDocumentChunk

PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION = 1


class PersistentVectorIndexContent(BaseModel):
    """Canonical searchable state sealed by one snapshot digest."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: int = Field(
        default=PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION,
        ge=PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION,
        le=PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION,
    )
    index_id: str
    generation: int = Field(ge=1)
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime
    records: list[EmbeddedDocumentChunk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not self.index_id.strip():
            raise ValueError("index_id must not be blank")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model must not be blank")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be before created_at")

        chunk_ids = [item.chunk.chunk_id.strip().casefold() for item in self.records]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("persistent index chunk IDs must be unique")
        if chunk_ids != sorted(chunk_ids):
            raise ValueError("persistent index records must be ordered by chunk_id")

        for item in self.records:
            embedding = item.embedding
            if embedding.model_name != self.embedding_model:
                raise ValueError(
                    "all index records must use the snapshot embedding_model"
                )
            if embedding.dimensions != self.embedding_dimensions:
                raise ValueError(
                    "all index records must use the snapshot embedding_dimensions"
                )
            if len(embedding.vector) != self.embedding_dimensions:
                raise ValueError("all index vectors must match embedding_dimensions")
            if not all(math.isfinite(value) for value in embedding.vector):
                raise ValueError("all index vector values must be finite")

        try:
            canonical_vector_index_content(self)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "persistent index content must be JSON serializable"
            ) from error
        return self


def canonical_vector_index_content(content: PersistentVectorIndexContent) -> bytes:
    """Return stable UTF-8 JSON bytes used for integrity checks."""

    if not isinstance(content, PersistentVectorIndexContent):
        raise TypeError("content must be PersistentVectorIndexContent")
    payload = content.model_dump(mode="json")
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return serialized.encode("utf-8")


def calculate_vector_index_content_sha256(
    content: PersistentVectorIndexContent,
) -> str:
    """Calculate the canonical snapshot content digest."""

    return hashlib.sha256(canonical_vector_index_content(content)).hexdigest()


class PersistentVectorIndexSnapshot(BaseModel):
    """One integrity-checked persistent vector-index generation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    content: PersistentVectorIndexContent
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        expected = calculate_vector_index_content_sha256(self.content)
        if not hmac.compare_digest(self.content_sha256, expected):
            raise ValueError(
                "content_sha256 must match canonical persistent index content"
            )
        return self

    @classmethod
    def seal(
        cls,
        content: PersistentVectorIndexContent,
    ) -> PersistentVectorIndexSnapshot:
        """Create a snapshot with the correct canonical digest."""

        if not isinstance(content, PersistentVectorIndexContent):
            raise TypeError("content must be PersistentVectorIndexContent")
        return cls(
            content=content,
            content_sha256=calculate_vector_index_content_sha256(content),
        )
