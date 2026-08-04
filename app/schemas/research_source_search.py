"""Schemas for research source search execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)


class ResearchSourceSearchStatus(StrEnum):
    """Outcome of one source search execution."""

    SUCCEEDED = "succeeded"
    NO_RESULTS = "no_results"
    FAILED = "failed"


class ResearchSourceSearchError(BaseModel):
    """Structured error produced by a search provider."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    error_type: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        """Validate search error details."""

        if not self.error_type.strip():
            raise ValueError(
                "error_type must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        return self


class ResearchSourceSearchResult(BaseModel):
    """Result of executing one research source search."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    query: ResearchSearchQuery
    status: ResearchSourceSearchStatus
    provider: str
    candidates: list[
        ResearchSourceCandidate
    ] = Field(default_factory=list)
    error: ResearchSourceSearchError | None = None
    duration_ms: int = Field(ge=0)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate status, candidates, and errors."""

        if not self.provider.strip():
            raise ValueError(
                "provider must not be blank"
            )

        for candidate in self.candidates:
            if (
                candidate.request_id
                != self.query.request_id
            ):
                raise ValueError(
                    "candidate request_id must match "
                    "the search query request_id"
                )

            if candidate.task_id != self.query.task_id:
                raise ValueError(
                    "candidate task_id must match "
                    "the search query task_id"
                )

            if candidate.query_id != self.query.query_id:
                raise ValueError(
                    "candidate query_id must match "
                    "the search query query_id"
                )

        normalized_source_ids = [
            candidate.source_id.strip().casefold()
            for candidate in self.candidates
        ]

        if len(set(normalized_source_ids)) != len(
            normalized_source_ids
        ):
            raise ValueError(
                "search result source IDs must be unique"
            )

        normalized_urls = [
            candidate.normalized_url()
            for candidate in self.candidates
        ]

        if len(set(normalized_urls)) != len(
            normalized_urls
        ):
            raise ValueError(
                "search result candidate URLs must be unique"
            )

        ranks = [
            candidate.rank
            for candidate in self.candidates
        ]

        if len(set(ranks)) != len(ranks):
            raise ValueError(
                "search result candidate ranks "
                "must be unique"
            )

        if (
            self.status
            is ResearchSourceSearchStatus.SUCCEEDED
        ):
            if not self.candidates:
                raise ValueError(
                    "succeeded search must contain "
                    "at least one candidate"
                )

            if self.error is not None:
                raise ValueError(
                    "succeeded search must not "
                    "contain an error"
                )

        elif (
            self.status
            is ResearchSourceSearchStatus.NO_RESULTS
        ):
            if self.candidates:
                raise ValueError(
                    "no-results search must not "
                    "contain candidates"
                )

            if self.error is not None:
                raise ValueError(
                    "no-results search must not "
                    "contain an error"
                )

        elif (
            self.status
            is ResearchSourceSearchStatus.FAILED
        ):
            if self.candidates:
                raise ValueError(
                    "failed search must not "
                    "contain candidates"
                )

            if self.error is None:
                raise ValueError(
                    "failed search must contain an error"
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
