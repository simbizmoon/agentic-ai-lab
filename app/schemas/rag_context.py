"""Schemas for grounded RAG context and citations."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RagCitation(BaseModel):
    """A citation pointing to one retrieved document Chunk."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    score: float = Field(ge=-1.0, le=1.0)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    source: str | None = None

    @model_validator(mode="after")
    def validate_character_range(self) -> RagCitation:
        """Ensure the citation source range is valid."""

        if self.end_char <= self.start_char:
            raise ValueError(
                "citation end_char must be greater than start_char"
            )

        return self


class RagContext(BaseModel):
    """Formatted retrieval context and its citations."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    context_text: str
    citations: list[RagCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_context(self) -> RagContext:
        """Ensure context and citations are consistent."""

        if self.citations and not self.context_text.strip():
            raise ValueError(
                "RAG context text is required when citations exist"
            )

        if not self.citations and self.context_text:
            raise ValueError(
                "RAG context text must be empty without citations"
            )

        citation_ids = [
            citation.citation_id
            for citation in self.citations
        ]

        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError(
                "RAG citation IDs must be unique"
            )

        return self
