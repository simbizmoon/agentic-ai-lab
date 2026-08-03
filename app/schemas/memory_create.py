"""Schema for creating structured agent memories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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


class MemoryCreate(BaseModel):
    """Caller-supplied values for a new memory."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    kind: MemoryKind
    scope: MemoryScope
    source: MemorySource
    content: str
    subject_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    source_reference: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_create(self) -> MemoryCreate:
        """Validate content, identifiers, tags, scope, and source."""

        if not self.content.strip():
            raise ValueError(
                "memory content must not be blank"
            )

        optional_values = {
            "subject_id": self.subject_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "source_reference": self.source_reference,
        }

        for name, value in optional_values.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if any(not tag.strip() for tag in self.tags):
            raise ValueError(
                "memory tags must not be blank"
            )

        normalized_tags = [
            tag.strip().casefold()
            for tag in self.tags
        ]

        if len(normalized_tags) != len(
            set(normalized_tags)
        ):
            raise ValueError(
                "memory tags must be unique"
            )

        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError(
                    "expires_at must be timezone-aware"
                )

            if (
                self.expires_at.utcoffset()
                != UTC.utcoffset(self.expires_at)
            ):
                raise ValueError(
                    "expires_at must use UTC"
                )

        if (
            self.scope is MemoryScope.SESSION
            and self.session_id is None
        ):
            raise ValueError(
                "session-scoped memory requires session_id"
            )

        if (
            self.scope is MemoryScope.USER
            and self.subject_id is None
        ):
            raise ValueError(
                "user-scoped memory requires subject_id"
            )

        if (
            self.scope is MemoryScope.PROJECT
            and self.project_id is None
        ):
            raise ValueError(
                "project-scoped memory requires project_id"
            )

        sources_requiring_reference = {
            MemorySource.TOOL_RESULT,
            MemorySource.AGENT_INFERENCE,
            MemorySource.IMPORTED_DOCUMENT,
        }

        if (
            self.source in sources_requiring_reference
            and self.source_reference is None
        ):
            raise ValueError(
                "memory source requires source_reference"
            )

        return self
