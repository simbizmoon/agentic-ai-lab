"""Schemas for filtering structured agent memories."""

from __future__ import annotations

from datetime import UTC, datetime

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


class MemoryQuery(BaseModel):
    """Filters used when listing memory records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    kinds: list[MemoryKind] = Field(default_factory=list)
    scopes: list[MemoryScope] = Field(default_factory=list)
    sources: list[MemorySource] = Field(default_factory=list)
    subject_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    include_expired: bool = False
    minimum_importance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    minimum_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    created_after: datetime | None = None
    created_before: datetime | None = None

    @model_validator(mode="after")
    def validate_query(self) -> MemoryQuery:
        """Validate query identifiers, tags, and timestamps."""

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

        if any(not tag.strip() for tag in self.tags):
            raise ValueError(
                "query tags must not be blank"
            )

        normalized_tags = [
            tag.strip().casefold()
            for tag in self.tags
        ]

        if len(normalized_tags) != len(
            set(normalized_tags)
        ):
            raise ValueError(
                "query tags must be unique"
            )

        for name, value in {
            "created_after": self.created_after,
            "created_before": self.created_before,
        }.items():
            if value is None:
                continue

            if value.tzinfo is None:
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

            if value.utcoffset() != UTC.utcoffset(value):
                raise ValueError(
                    f"{name} must use UTC"
                )

        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError(
                "created_after must not be later than created_before"
            )

        return self
