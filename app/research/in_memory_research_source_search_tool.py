"""In-memory implementation of the research source search port."""

from __future__ import annotations

import re
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

from app.research.research_source_search_tool import (
    ResearchSourceSearchTool,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_search import (
    ResearchSourceSearchResult,
    ResearchSourceSearchStatus,
)


class InMemoryResearchSourceSearchTool(
    ResearchSourceSearchTool
):
    """Search deterministic source records held in memory."""

    _TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

    def __init__(
        self,
        *,
        records: list[InMemoryResearchSourceRecord],
        name: str = "in_memory_source_search",
        provider: str = "in-memory",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "name must not be blank"
            )

        if not provider.strip():
            raise ValueError(
                "provider must not be blank"
            )

        self._validate_records(records)

        self._records = [
            record.model_copy(deep=True)
            for record in records
        ]
        self._name = name
        self._provider = provider

    @property
    def name(self) -> str:
        """Return the search tool name."""

        return self._name

    @property
    def provider(self) -> str:
        """Return the in-memory provider name."""

        return self._provider

    def search(
        self,
        query: ResearchSearchQuery,
    ) -> ResearchSourceSearchResult:
        """Search records and return deterministic candidates."""

        started_at = perf_counter()

        query_tokens = self._tokens(
            query.query_text
        )

        matches: list[
            tuple[
                int,
                int,
                InMemoryResearchSourceRecord,
            ]
        ] = []

        for position, record in enumerate(
            self._records
        ):
            if not self._matches_constraints(
                query=query,
                record=record,
            ):
                continue

            score = self._relevance_score(
                query_tokens=query_tokens,
                record=record,
            )

            if score <= 0:
                continue

            matches.append(
                (
                    score,
                    position,
                    record,
                )
            )

        matches.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        selected = matches[
            : query.maximum_results
        ]

        duration_ms = max(
            0,
            int(
                (perf_counter() - started_at)
                * 1000
            ),
        )

        if not selected:
            return ResearchSourceSearchResult(
                query=query,
                status=(
                    ResearchSourceSearchStatus.NO_RESULTS
                ),
                provider=self.provider,
                candidates=[],
                error=None,
                duration_ms=duration_ms,
                metadata={
                    "tool": self.name,
                    "record_count": str(
                        len(self._records)
                    ),
                },
            )

        candidates = [
            self._candidate(
                query=query,
                record=record,
                rank=rank,
                score=score,
            )
            for rank, (
                score,
                _,
                record,
            ) in enumerate(
                selected,
                start=1,
            )
        ]

        return ResearchSourceSearchResult(
            query=query,
            status=(
                ResearchSourceSearchStatus.SUCCEEDED
            ),
            provider=self.provider,
            candidates=candidates,
            error=None,
            duration_ms=duration_ms,
            metadata={
                "tool": self.name,
                "record_count": str(
                    len(self._records)
                ),
                "matched_count": str(
                    len(matches)
                ),
            },
        )

    def records(
        self,
    ) -> list[InMemoryResearchSourceRecord]:
        """Return defensive copies of stored records."""

        return [
            record.model_copy(deep=True)
            for record in self._records
        ]

    def _matches_constraints(
        self,
        *,
        query: ResearchSearchQuery,
        record: InMemoryResearchSourceRecord,
    ) -> bool:
        """Check source type and date constraints."""

        if (
            query.preferred_source_types
            and record.source_type
            not in query.preferred_source_types
        ):
            return False

        if (
            query.start_date is not None
            and (
                record.published_at is None
                or record.published_at
                < query.start_date
            )
        ):
            return False

        return not (
            query.end_date is not None
            and (
                record.published_at is None
                or record.published_at
                > query.end_date
            )
        )

    def _relevance_score(
        self,
        *,
        query_tokens: set[str],
        record: InMemoryResearchSourceRecord,
    ) -> int:
        """Return a deterministic token-overlap score."""

        title_tokens = self._tokens(
            record.title
        )
        snippet_tokens = self._tokens(
            record.snippet
        )
        keyword_tokens = {
            token
            for keyword in record.keywords
            for token in self._tokens(keyword)
        }

        title_matches = len(
            query_tokens & title_tokens
        )
        keyword_matches = len(
            query_tokens & keyword_tokens
        )
        snippet_matches = len(
            query_tokens & snippet_tokens
        )

        return (
            title_matches * 3
            + keyword_matches * 2
            + snippet_matches
        )

    def _candidate(
        self,
        *,
        query: ResearchSearchQuery,
        record: InMemoryResearchSourceRecord,
        rank: int,
        score: int,
    ) -> ResearchSourceCandidate:
        """Convert one record into a query-scoped candidate."""

        return ResearchSourceCandidate(
            source_id=record.source_id,
            request_id=query.request_id,
            task_id=query.task_id,
            query_id=query.query_id,
            title=record.title,
            url=record.url,
            source_type=record.source_type,
            snippet=record.snippet,
            author=record.author,
            publisher=record.publisher,
            published_at=record.published_at,
            rank=rank,
            metadata={
                **record.metadata,
                "provider": self.provider,
                "relevance_score": str(score),
            },
        )

    @classmethod
    def _tokens(
        cls,
        value: str,
    ) -> set[str]:
        """Return normalized alphanumeric tokens."""

        return set(
            cls._TOKEN_PATTERN.findall(
                value.casefold()
            )
        )

    @classmethod
    def _validate_records(
        cls,
        records: list[InMemoryResearchSourceRecord],
    ) -> None:
        """Validate source identity and URL uniqueness."""

        normalized_source_ids = [
            record.source_id.strip().casefold()
            for record in records
        ]

        if len(set(normalized_source_ids)) != len(
            normalized_source_ids
        ):
            raise ValueError(
                "record source IDs must be unique"
            )

        normalized_urls = [
            cls._normalized_url(record.url)
            for record in records
        ]

        if len(set(normalized_urls)) != len(
            normalized_urls
        ):
            raise ValueError(
                "record URLs must be unique"
            )

    @staticmethod
    def _normalized_url(url: str) -> str:
        """Return a normalized URL for record validation."""

        parsed = urlsplit(url.strip())
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
