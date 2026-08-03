"""Schemas for ranked memory-search results."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.memory_record import MemoryRecord


class MemoryScoreBreakdown(BaseModel):
    """Individual components of a memory relevance score."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    content_overlap: float = Field(
        ge=0.0,
        le=1.0,
    )
    tag_overlap: float = Field(
        ge=0.0,
        le=1.0,
    )
    phrase_match: float = Field(
        ge=0.0,
        le=1.0,
    )
    importance: float = Field(
        ge=0.0,
        le=1.0,
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class MemorySearchResult(BaseModel):
    """One ranked memory-search result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    memory: MemoryRecord
    score: float = Field(
        ge=0.0,
        le=1.0,
    )
    matched_terms: list[str]
    breakdown: MemoryScoreBreakdown

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> MemorySearchResult:
        """Validate matched terms."""

        if any(
            not term.strip()
            for term in self.matched_terms
        ):
            raise ValueError(
                "matched terms must not be blank"
            )

        normalized_terms = [
            term.casefold()
            for term in self.matched_terms
        ]

        if len(normalized_terms) != len(
            set(normalized_terms)
        ):
            raise ValueError(
                "matched terms must be unique"
            )

        return self
