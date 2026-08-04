"""Schemas for source records stored by an in-memory search adapter."""

from __future__ import annotations

from datetime import date
from typing import Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_request import ResearchSourceType


class InMemoryResearchSourceRecord(BaseModel):
    """One searchable source record stored in memory."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    title: str
    url: str
    source_type: ResearchSourceType
    snippet: str = ""
    keywords: list[str] = Field(default_factory=list)
    author: str | None = None
    publisher: str | None = None
    published_at: date | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate record identity, URL, and searchable text."""

        required_text = {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        parsed = urlsplit(self.url.strip())

        if parsed.scheme.casefold() not in {
            "http",
            "https",
        }:
            raise ValueError(
                "url must use http or https"
            )

        if not parsed.netloc:
            raise ValueError(
                "url must contain a host"
            )

        normalized_keywords: list[str] = []

        for keyword in self.keywords:
            if not keyword.strip():
                raise ValueError(
                    "keywords must not contain blank values"
                )

            normalized_keywords.append(
                keyword.strip().casefold()
            )

        if len(set(normalized_keywords)) != len(
            normalized_keywords
        ):
            raise ValueError(
                "keywords must not contain duplicates"
            )

        optional_text = {
            "author": self.author,
            "publisher": self.publisher,
        }

        for name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank when provided"
                )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self
