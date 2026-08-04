"""Schemas for structured research requests."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResearchDepth(StrEnum):
    """Requested depth of a research workflow."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchOutputFormat(StrEnum):
    """Requested format of the final research result."""

    BRIEF = "brief"
    DETAILED_REPORT = "detailed_report"
    COMPARISON = "comparison"


class ResearchSourceType(StrEnum):
    """Preferred source categories for research."""

    OFFICIAL_DOCUMENTATION = "official_documentation"
    PRIMARY_RESEARCH = "primary_research"
    GOVERNMENT = "government"
    ACADEMIC = "academic"
    INDUSTRY = "industry"
    NEWS = "news"
    OTHER = "other"


class ResearchRequest(BaseModel):
    """Validated user request for one research workflow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    question: str
    objective: str
    depth: ResearchDepth = ResearchDepth.STANDARD
    output_format: ResearchOutputFormat = (
        ResearchOutputFormat.DETAILED_REPORT
    )
    include_topics: list[str] = Field(
        default_factory=list
    )
    exclude_topics: list[str] = Field(
        default_factory=list
    )
    preferred_source_types: list[
        ResearchSourceType
    ] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    maximum_sources: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    require_citations: bool = True
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate text, ranges, uniqueness, and scope."""

        required_text = {
            "request_id": self.request_id,
            "question": self.question,
            "objective": self.objective,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        self._validate_unique_text_values(
            name="include_topics",
            values=self.include_topics,
        )
        self._validate_unique_text_values(
            name="exclude_topics",
            values=self.exclude_topics,
        )

        include_keys = {
            value.strip().casefold()
            for value in self.include_topics
        }
        exclude_keys = {
            value.strip().casefold()
            for value in self.exclude_topics
        }

        overlap = include_keys & exclude_keys

        if overlap:
            raise ValueError(
                "include_topics and exclude_topics "
                "must not overlap"
            )

        if len(set(self.preferred_source_types)) != len(
            self.preferred_source_types
        ):
            raise ValueError(
                "preferred_source_types must not "
                "contain duplicates"
            )

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError(
                "start_date must not be after end_date"
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

    @staticmethod
    def _validate_unique_text_values(
        *,
        name: str,
        values: list[str],
    ) -> None:
        """Validate nonblank, normalized-unique text items."""

        normalized: list[str] = []

        for value in values:
            if not value.strip():
                raise ValueError(
                    f"{name} must not contain blank values"
                )

            normalized.append(
                value.strip().casefold()
            )

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{name} must not contain duplicates"
            )
