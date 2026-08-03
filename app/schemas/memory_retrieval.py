"""Schemas for end-to-end agent memory retrieval."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
    MemorySource,
)


class MemoryRetrievalRequest(BaseModel):
    """Values used for memory search and context construction."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    query: str
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    context_limit: int = Field(
        default=5,
        ge=1,
        le=50,
    )
    minimum_search_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
    )
    minimum_context_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
    )
    maximum_content_characters: int = Field(
        default=800,
        ge=50,
        le=10_000,
    )
    kinds: list[MemoryKind] | None = None
    scopes: list[MemoryScope] | None = None
    sources: list[MemorySource] | None = None
    subject_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    include_expired: bool = False
    include_tags: bool = True
    include_source_reference: bool = True
    record_access: bool = False

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> MemoryRetrievalRequest:
        """Validate query, limits, and identifiers."""

        if not self.query.strip():
            raise ValueError(
                "memory retrieval query must not be blank"
            )

        if self.context_limit > self.search_limit:
            raise ValueError(
                "context_limit must not exceed search_limit"
            )

        optional_identifiers = {
            "subject_id": self.subject_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
        }

        for name, value in optional_identifiers.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        return self
