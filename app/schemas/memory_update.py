"""Schema for updating mutable memory fields."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class MemoryUpdate(BaseModel):
    """Mutable values for an existing memory record."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    content: str | None = None
    tags: list[str] | None = None
    importance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    source_reference: str | None = None
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> MemoryUpdate:
        """Validate mutable fields."""

        if self.content is not None and not self.content.strip():
            raise ValueError(
                "memory content must not be blank"
            )

        if (
            self.source_reference is not None
            and not self.source_reference.strip()
        ):
            raise ValueError(
                "source_reference must not be blank"
            )

        if self.tags is not None:
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

        for name, value in {
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
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

        if not self.model_fields_set:
            raise ValueError(
                "memory update must contain at least one field"
            )

        return self
