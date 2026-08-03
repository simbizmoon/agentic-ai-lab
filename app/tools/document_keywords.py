"""Deterministic keyword extraction for document text."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentKeywordsInput(BaseModel):
    """Validated input for deterministic keyword extraction."""

    model_config = ConfigDict(extra="forbid", strict=True)

    document_text: str = Field(min_length=1)
    max_keywords: int = Field(default=5, ge=1, le=20)

    @field_validator("document_text")
    @classmethod
    def reject_whitespace_only_text(cls, value: str) -> str:
        """Reject input containing only whitespace."""

        if not value.strip():
            raise ValueError(
                "document_text must not contain only whitespace"
            )

        return value


class KeywordCount(BaseModel):
    """One keyword and its occurrence count."""

    model_config = ConfigDict(extra="forbid", strict=True)

    keyword: str
    count: int = Field(ge=1)


class DocumentKeywords(BaseModel):
    """Structured keyword extraction result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    keywords: list[KeywordCount]


def extract_document_keywords(
    tool_input: DocumentKeywordsInput,
) -> DocumentKeywords:
    """Extract frequent normalized words from document text."""

    words = re.findall(
        r"[A-Za-z0-9가-힣]+",
        tool_input.document_text.lower(),
    )

    counts = Counter(words)

    ranked_words = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    keywords = [
        KeywordCount(
            keyword=word,
            count=count,
        )
        for word, count in ranked_words[
            : tool_input.max_keywords
        ]
    ]

    return DocumentKeywords(keywords=keywords)
