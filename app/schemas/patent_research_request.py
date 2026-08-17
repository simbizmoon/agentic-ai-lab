"""User request contract for bounded patent technical-relevance research."""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.http_html_reader_config import HttpHtmlReaderConfig


class PatentResearchRequest(BaseModel):
    """Describe one bounded patent technical-relevance request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    question: str
    objective: str
    prior_art_cutoff_date: date | None = None
    maximum_search_results: int = Field(default=8, ge=1, le=8)
    maximum_sources: int = Field(default=4, ge=1, le=4)
    maximum_bytes: int = HttpHtmlReaderConfig().maximum_bytes

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate text, source bounds, and the shared Web byte policy."""

        if not self.question.strip():
            raise ValueError("question must not be blank")
        if not self.objective.strip():
            raise ValueError("objective must not be blank")
        if self.maximum_sources > self.maximum_search_results:
            raise ValueError("maximum_sources must not exceed maximum_search_results")

        # Keep the patent slice on the authoritative Web-reader byte contract.
        HttpHtmlReaderConfig(maximum_bytes=self.maximum_bytes)
        return self
