"""Tavily implementation of the research source search port."""

from __future__ import annotations

from hashlib import sha256
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.research.research_source_search_tool import ResearchSourceSearchTool
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import ResearchSearchQuery
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_search import (
    ResearchSourceSearchError,
    ResearchSourceSearchResult,
    ResearchSourceSearchStatus,
)
from app.schemas.tavily_search_config import TavilySearchConfig


class TavilySearchResponseItem(BaseModel):
    """One validated Tavily search result."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    title: str
    url: str
    content: str = ""
    score: float | int | None = None


class TavilySearchUsage(BaseModel):
    """Optional Tavily credit usage."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    credits: float | int | None = None


class TavilySearchResponse(BaseModel):
    """Validated subset of a Tavily search response."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    query: str
    results: list[TavilySearchResponseItem] = Field(default_factory=list)
    response_time: float | int | None = None
    request_id: str | None = None
    usage: TavilySearchUsage | None = None


class TavilyResearchSourceSearchTool(ResearchSourceSearchTool):
    """Search live web sources through Tavily."""

    def __init__(
        self,
        *,
        config: TavilySearchConfig,
        client: httpx.Client | None = None,
        name: str = "tavily_source_search",
        provider: str = "tavily",
    ) -> None:
        if not name.strip():
            raise ValueError("name must not be blank")
        if not provider.strip():
            raise ValueError("provider must not be blank")

        self._config = config
        self._client = client
        self._name = name
        self._provider = provider

    @property
    def name(self) -> str:
        """Return the search tool name."""

        return self._name

    @property
    def provider(self) -> str:
        """Return the provider name."""

        return self._provider

    def search(self, query: ResearchSearchQuery) -> ResearchSourceSearchResult:
        """Execute one Tavily search request."""

        started_at = perf_counter()

        try:
            response = self._post(query)
            response.raise_for_status()
            parsed = TavilySearchResponse.model_validate(response.json())
            candidates = self._candidates(query=query, response=parsed)
        except httpx.TimeoutException:
            return self._failed_result(
                query=query,
                started_at=started_at,
                error_type="SearchTimeout",
                message="Tavily search timed out.",
                retryable=True,
            )
        except httpx.RequestError:
            return self._failed_result(
                query=query,
                started_at=started_at,
                error_type="SearchNetworkError",
                message="Tavily search could not reach the provider.",
                retryable=True,
            )
        except httpx.HTTPStatusError as exc:
            return self._http_failure(
                query=query,
                started_at=started_at,
                response=exc.response,
            )
        except (ValueError, ValidationError):
            return self._failed_result(
                query=query,
                started_at=started_at,
                error_type="SearchResponseValidationError",
                message="Tavily returned an invalid search response.",
                retryable=False,
            )

        metadata = self._response_metadata(parsed)

        if not candidates:
            return ResearchSourceSearchResult(
                query=query,
                status=ResearchSourceSearchStatus.NO_RESULTS,
                provider=self.provider,
                candidates=[],
                error=None,
                duration_ms=self._duration_ms(started_at),
                metadata=metadata,
            )

        return ResearchSourceSearchResult(
            query=query,
            status=ResearchSourceSearchStatus.SUCCEEDED,
            provider=self.provider,
            candidates=candidates,
            error=None,
            duration_ms=self._duration_ms(started_at),
            metadata=metadata,
        )

    def _post(self, query: ResearchSearchQuery) -> httpx.Response:
        """Send one Tavily REST request."""

        headers = {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        if self._config.project_id is not None:
            headers["X-Project-ID"] = self._config.project_id

        payload: dict[str, Any] = {
            "query": query.query_text.strip(),
            "topic": "general",
            "search_depth": "basic",
            "auto_parameters": False,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_usage": True,
            "max_results": min(
                query.maximum_results,
                self._config.maximum_results,
            ),
        }

        if query.start_date is not None:
            payload["start_date"] = query.start_date.isoformat()
        if query.end_date is not None:
            payload["end_date"] = query.end_date.isoformat()

        if self._client is not None:
            return self._client.post(
                self._config.search_url,
                headers=headers,
                json=payload,
                timeout=self._config.timeout_seconds,
            )

        with httpx.Client() as client:
            return client.post(
                self._config.search_url,
                headers=headers,
                json=payload,
                timeout=self._config.timeout_seconds,
            )

    def _candidates(
        self,
        *,
        query: ResearchSearchQuery,
        response: TavilySearchResponse,
    ) -> list[ResearchSourceCandidate]:
        """Map unique valid Tavily results to candidates."""

        candidates: list[ResearchSourceCandidate] = []
        seen_urls: set[str] = set()
        limit = min(query.maximum_results, self._config.maximum_results)

        for item in response.results:
            if len(candidates) >= limit:
                break
            if not self._valid_http_url(item.url):
                continue
            if not item.title.strip():
                continue

            normalized_url = self._normalized_url(item.url)
            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)
            rank = len(candidates) + 1
            metadata = {"provider": self.provider}

            if item.score is not None:
                metadata["provider_score"] = str(item.score)

            candidates.append(
                ResearchSourceCandidate(
                    source_id=self._source_id(
                        query=query,
                        normalized_url=normalized_url,
                    ),
                    request_id=query.request_id,
                    task_id=query.task_id,
                    query_id=query.query_id,
                    title=item.title.strip(),
                    url=item.url.strip(),
                    source_type=ResearchSourceType.OTHER,
                    snippet=item.content.strip(),
                    rank=rank,
                    metadata=metadata,
                )
            )

        return candidates

    def _http_failure(
        self,
        *,
        query: ResearchSearchQuery,
        started_at: float,
        response: httpx.Response,
    ) -> ResearchSourceSearchResult:
        """Map one HTTP failure to a safe result."""

        status = response.status_code

        if status == 400:
            error_type, retryable = "SearchRequestValidationError", False
        elif status in {401, 403}:
            error_type, retryable = "SearchAuthenticationError", False
        elif status == 429:
            error_type, retryable = "SearchRateLimitError", True
        elif status >= 500:
            error_type, retryable = "SearchProviderError", True
        else:
            error_type, retryable = "SearchHttpError", False

        metadata = {
            "tool": self.name,
            "http_status": str(status),
        }

        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.strip():
            metadata["retry_after"] = retry_after.strip()

        return self._failed_result(
            query=query,
            started_at=started_at,
            error_type=error_type,
            message=f"Tavily search request failed with HTTP status {status}.",
            retryable=retryable,
            metadata=metadata,
        )

    def _failed_result(
        self,
        *,
        query: ResearchSearchQuery,
        started_at: float,
        error_type: str,
        message: str,
        retryable: bool,
        metadata: dict[str, str] | None = None,
    ) -> ResearchSourceSearchResult:
        """Create a structured failed result."""

        safe_metadata = {"tool": self.name, **(metadata or {})}

        return ResearchSourceSearchResult(
            query=query,
            status=ResearchSourceSearchStatus.FAILED,
            provider=self.provider,
            candidates=[],
            error=ResearchSourceSearchError(
                error_type=error_type,
                message=message,
                retryable=retryable,
            ),
            duration_ms=self._duration_ms(started_at),
            metadata=safe_metadata,
        )

    def _response_metadata(
        self,
        response: TavilySearchResponse,
    ) -> dict[str, str]:
        """Return safe normalized provider metadata."""

        metadata = {
            "tool": self.name,
            "provider_query": response.query,
        }

        if response.request_id is not None and response.request_id.strip():
            metadata["request_id"] = response.request_id.strip()
        if response.response_time is not None:
            metadata["response_time"] = str(response.response_time)
        if response.usage is not None and response.usage.credits is not None:
            metadata["usage_credits"] = str(response.usage.credits)

        return metadata

    @staticmethod
    def _source_id(
        *,
        query: ResearchSearchQuery,
        normalized_url: str,
    ) -> str:
        """Return a deterministic query-scoped source ID."""

        digest = sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
        return f"{query.query_id.strip()}-source-{digest}"

    @staticmethod
    def _valid_http_url(url: str) -> bool:
        """Return whether a URL is a supported web URL."""

        if not url.strip():
            return False

        parsed = urlsplit(url.strip())
        return (
            parsed.scheme.casefold() in {"http", "https"}
            and bool(parsed.netloc)
        )

    @staticmethod
    def _normalized_url(url: str) -> str:
        """Normalize a URL through the domain schema."""

        candidate = ResearchSourceCandidate(
            source_id="normalization-source",
            request_id="normalization-request",
            task_id="normalization-task",
            query_id="normalization-query",
            title="Normalization",
            url=url,
            source_type=ResearchSourceType.OTHER,
            rank=1,
        )
        return candidate.normalized_url()

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        """Return nonnegative elapsed milliseconds."""

        return max(0, int((perf_counter() - started_at) * 1000))
