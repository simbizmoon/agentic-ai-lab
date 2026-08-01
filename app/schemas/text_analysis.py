from __future__ import annotations

from enum import Enum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

Keyword = Annotated[str, Field(min_length=1, max_length=50)]
ReviewReason = Annotated[str, Field(min_length=1, max_length=300)]


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class TextAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=300)
    sentiment: Sentiment
    keywords: list[Keyword] = Field(min_length=1, max_length=5)
    requires_review: StrictBool
    review_reason: ReviewReason | None

    @field_validator("topic", "summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        return normalized

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        normalized_keywords: list[str] = []
        seen_keywords: set[str] = set()

        for keyword in value:
            normalized_keyword = keyword.strip()
            if not normalized_keyword:
                raise ValueError("keyword must not be empty")

            keyword_key = normalized_keyword.casefold()
            if keyword_key in seen_keywords:
                raise ValueError("keywords must not contain duplicates")

            seen_keywords.add(keyword_key)
            normalized_keywords.append(normalized_keyword)

        return normalized_keywords

    @field_validator("review_reason")
    @classmethod
    def normalize_review_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            raise ValueError("review_reason must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_review_reason_policy(self) -> Self:
        if self.requires_review and self.review_reason is None:
            raise ValueError("review_reason is required when requires_review is true")

        if not self.requires_review and self.review_reason is not None:
            raise ValueError("review_reason must be None when requires_review is false")

        return self
