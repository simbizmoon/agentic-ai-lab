"""Schemas for normalized research source candidates."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)


class ResearchSourceCandidateStatus(StrEnum):
    """Processing state of one source candidate."""

    DISCOVERED = "discovered"
    SELECTED = "selected"
    REJECTED = "rejected"
    READ = "read"
    FAILED = "failed"


class ResearchSourceCandidate(BaseModel):
    """One normalized source discovered by a search query."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    request_id: str
    task_id: str
    query_id: str
    title: str
    url: str
    source_type: ResearchSourceType
    snippet: str = ""
    author: str | None = None
    publisher: str | None = None
    published_at: date | None = None
    rank: int = Field(ge=1)
    status: ResearchSourceCandidateStatus = (
        ResearchSourceCandidateStatus.DISCOVERED
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        """Validate source identity, URL, and optional text."""

        required_text = {
            "source_id": self.source_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "query_id": self.query_id,
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

    def normalized_url(self) -> str:
        """Return a normalized URL for duplicate checks."""

        parsed = urlsplit(self.url.strip())

        scheme = parsed.scheme.casefold()
        hostname = (
            parsed.hostname.casefold()
            if parsed.hostname is not None
            else ""
        )

        port = parsed.port

        if (
            port is not None
            and not (
                scheme == "http"
                and port == 80
            )
            and not (
                scheme == "https"
                and port == 443
            )
        ):
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        path = parsed.path or "/"

        if path != "/":
            path = path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                parsed.query,
                "",
            )
        )


class ResearchSourceCandidateSet(BaseModel):
    """Validated candidates returned for a query set."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    query_set: ResearchSearchQuerySet
    candidates: list[ResearchSourceCandidate] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        """Validate candidate identities and query references."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        if self.query_set.request_id != self.request_id:
            raise ValueError(
                "query set request_id must match "
                "candidate set request_id"
            )

        normalized_source_ids = [
            candidate.source_id.strip().casefold()
            for candidate in self.candidates
        ]

        if len(set(normalized_source_ids)) != len(
            normalized_source_ids
        ):
            raise ValueError(
                "source IDs must be unique"
            )

        if any(
            candidate.request_id != self.request_id
            for candidate in self.candidates
        ):
            raise ValueError(
                "all candidate request IDs must match "
                "the candidate set request_id"
            )

        query_by_id = {
            query.query_id.strip().casefold(): query
            for query in self.query_set.queries
        }

        for candidate in self.candidates:
            query_key = (
                candidate.query_id.strip().casefold()
            )
            query = query_by_id.get(query_key)

            if query is None:
                raise ValueError(
                    "all candidates must reference "
                    "existing queries"
                )

            if (
                candidate.task_id.strip().casefold()
                != query.task_id.strip().casefold()
            ):
                raise ValueError(
                    "candidate task_id must match "
                    "the referenced query task_id"
                )

        url_keys = [
            (
                candidate.query_id.strip().casefold(),
                candidate.normalized_url(),
            )
            for candidate in self.candidates
        ]

        if len(set(url_keys)) != len(url_keys):
            raise ValueError(
                "candidates for the same query must not "
                "contain duplicate URLs"
            )

        rank_keys = [
            (
                candidate.query_id.strip().casefold(),
                candidate.rank,
            )
            for candidate in self.candidates
        ]

        if len(set(rank_keys)) != len(rank_keys):
            raise ValueError(
                "candidate ranks must be unique "
                "within each query"
            )

        return self

    def ordered_candidates(
        self,
    ) -> list[ResearchSourceCandidate]:
        """Return candidates in deterministic query and rank order."""

        query_positions = {
            query.query_id.strip().casefold(): position
            for position, query in enumerate(
                self.query_set.ordered_queries()
            )
        }
        original_positions = {
            candidate.source_id: position
            for position, candidate in enumerate(
                self.candidates
            )
        }

        return sorted(
            self.candidates,
            key=lambda candidate: (
                query_positions[
                    candidate.query_id.strip().casefold()
                ],
                candidate.rank,
                original_positions[candidate.source_id],
            ),
        )

    def candidates_for_query(
        self,
        query_id: str,
    ) -> list[ResearchSourceCandidate]:
        """Return ordered candidates for one query."""

        if not query_id.strip():
            raise ValueError(
                "query_id must not be blank"
            )

        normalized_query_id = (
            query_id.strip().casefold()
        )

        return [
            candidate
            for candidate in self.ordered_candidates()
            if candidate.query_id.strip().casefold()
            == normalized_query_id
        ]
