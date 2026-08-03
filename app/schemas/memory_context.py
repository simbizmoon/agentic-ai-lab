"""Schemas for memory context supplied to an agent prompt."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class MemoryContextItem(BaseModel):
    """One memory item selected for prompt context."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    memory_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    score: float = Field(
        ge=0.0,
        le=1.0,
    )
    tags: list[str] = Field(default_factory=list)
    source_reference: str | None = None

    @model_validator(mode="after")
    def validate_item(self) -> MemoryContextItem:
        """Validate identifiers, content, and tags."""

        if not self.memory_id.strip():
            raise ValueError(
                "memory_id must not be blank"
            )

        if not self.content.strip():
            raise ValueError(
                "memory context content must not be blank"
            )

        if (
            self.source_reference is not None
            and not self.source_reference.strip()
        ):
            raise ValueError(
                "source_reference must not be blank"
            )

        if any(not tag.strip() for tag in self.tags):
            raise ValueError(
                "memory context tags must not be blank"
            )

        normalized_tags = [
            tag.casefold()
            for tag in self.tags
        ]

        if len(normalized_tags) != len(
            set(normalized_tags)
        ):
            raise ValueError(
                "memory context tags must be unique"
            )

        return self


class MemoryContext(BaseModel):
    """Structured and rendered memory prompt context."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    query: str = Field(min_length=1)
    items: list[MemoryContextItem]
    rendered_text: str = Field(min_length=1)
    omitted_count: int = Field(
        default=0,
        ge=0,
    )
    was_truncated: bool = False

    @model_validator(mode="after")
    def validate_context(self) -> MemoryContext:
        """Validate query and rendered context."""

        if not self.query.strip():
            raise ValueError(
                "memory context query must not be blank"
            )

        if not self.rendered_text.strip():
            raise ValueError(
                "rendered memory context must not be blank"
            )

        if self.was_truncated != (
            self.omitted_count > 0
        ):
            raise ValueError(
                "truncation fields are inconsistent"
            )

        return self
