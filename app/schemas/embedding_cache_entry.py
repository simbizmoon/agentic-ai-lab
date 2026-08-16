"""Schemas for persistent text embedding cache entries."""

from __future__ import annotations

import hmac
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.report_integrity import is_valid_sha256_digest
from app.schemas.document_embedding import TextEmbedding

EMBEDDING_CACHE_ENTRY_VERSION = 1


class EmbeddingCacheEntry(BaseModel):
    """A versioned, content-addressed cached text embedding."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    version: Literal[EMBEDDING_CACHE_ENTRY_VERSION]
    cache_key: str
    text_sha256: str
    model_name: str = Field(min_length=1)
    dimensions: int = Field(gt=0)
    embedding: TextEmbedding

    @field_validator("cache_key", "text_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Require lowercase SHA-256 hexadecimal identities."""

        if not is_valid_sha256_digest(value):
            raise ValueError("value must be a lowercase SHA-256 digest")
        return value

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        """Reject blank model identifiers."""

        if not value.strip():
            raise ValueError("model_name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_embedding_identity(self) -> EmbeddingCacheEntry:
        """Ensure the embedded payload matches its cache identity."""

        if not hmac.compare_digest(
            self.embedding.model_name,
            self.model_name,
        ):
            raise ValueError("embedding model does not match cache entry")
        if self.embedding.dimensions != self.dimensions:
            raise ValueError("embedding dimensions do not match cache entry")
        return self
