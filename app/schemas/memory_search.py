"""Schemas for deterministic keyword memory search."""

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


class MemorySearchRequest(BaseModel):
    """Values used to retrieve relevant memories."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    query: str
    limit: int = Field(
        default=5,
        ge=1,
        le=100,
    )
    minimum_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
    )
    kinds: list[MemoryKind] | None = None
    scopes: list[MemoryScope] | None = None
    sources: list[MemorySource] | None = None
    subject_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    include_expired: bool = False

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> MemorySearchRequest:
        """Validate query and optional identifiers."""

        if not self.query.strip():
            raise ValueError(
                "memory search query must not be blank"
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
