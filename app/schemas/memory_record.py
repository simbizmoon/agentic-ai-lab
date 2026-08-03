"""Schemas for structured agent memory records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class MemoryKind(StrEnum):
    """High-level categories of agent memory."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryScope(StrEnum):
    """Entity boundary within which a memory is valid."""

    SESSION = "session"
    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"


class MemorySource(StrEnum):
    """Origin from which a memory was created."""

    USER_STATEMENT = "user_statement"
    TOOL_RESULT = "tool_result"
    AGENT_INFERENCE = "agent_inference"
    SYSTEM_EVENT = "system_event"
    IMPORTED_DOCUMENT = "imported_document"


class MemoryRecord(BaseModel):
    """One validated and retrievable agent memory."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    memory_id: str
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
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_memory(self) -> MemoryRecord:
        """Validate identifiers, timestamps, tags, and scope."""

        self._validate_non_blank_fields()
        self._validate_tags()
        self._validate_timestamps()
        self._validate_scope_identifiers()
        self._validate_source_requirements()

        return self

    def _validate_non_blank_fields(self) -> None:
        """Reject blank required and optional identifiers."""

        if not self.memory_id.strip():
            raise ValueError(
                "memory ID must not be blank"
            )

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

    def _validate_tags(self) -> None:
        """Require normalized and unique tag values."""

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

    def _validate_timestamps(self) -> None:
        """Require UTC-aware and chronologically valid timestamps."""

        timestamps = {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
        }

        for name, value in timestamps.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

            if (
                value is not None
                and value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError(
                    f"{name} must use UTC"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at must not precede created_at"
            )

        if (
            self.last_accessed_at is not None
            and self.last_accessed_at < self.created_at
        ):
            raise ValueError(
                "last_accessed_at must not precede created_at"
            )

        if (
            self.expires_at is not None
            and self.expires_at <= self.created_at
        ):
            raise ValueError(
                "expires_at must be later than created_at"
            )

    def _validate_scope_identifiers(self) -> None:
        """Require identifiers appropriate to the selected scope."""

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

    def _validate_source_requirements(self) -> None:
        """Require provenance for inferred or imported memories."""

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
