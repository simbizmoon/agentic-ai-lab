"""One-call Tavily binding for Stage 9 allowlisted official-web evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebDocument,
)

_MAXIMUM_DOCUMENT_BYTES = 512_000


class _TavilyResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    title: str
    url: str
    raw_content: str | None = None


class _TavilyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    results: list[_TavilyResult] = Field(default_factory=list)


class Stage9TavilyOfficialWebProviderError(RuntimeError):
    """Tavily failed or returned data outside the locked Stage 9 boundary."""


class Stage9TavilyOfficialWebProvider:
    """Fetch exact markdown from explicitly allowlisted official domains once."""

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        base_url: str = "https://api.tavily.com",
        timeout_seconds: float = 30.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be blank")
        if not base_url.strip():
            raise ValueError("base_url must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._api_key = api_key
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    def acquire(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> tuple[Stage9OfficialWebDocument, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")
        if not allowed_domains or any(not value.strip() for value in allowed_domains):
            raise ValueError("allowed_domains must contain nonblank domains")
        if maximum_results < 1 or maximum_results > 2:
            raise ValueError("maximum_results must be between 1 and 2")

        payload: dict[str, object] = {
            "query": normalized_query,
            "topic": "general",
            "search_depth": "basic",
            "auto_parameters": False,
            "include_answer": False,
            "include_raw_content": "markdown",
            "include_images": False,
            "include_usage": True,
            "max_results": maximum_results,
            "include_domains": list(allowed_domains),
        }
        try:
            response = self._post(payload)
            response.raise_for_status()
            envelope = _TavilyResponse.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise Stage9TavilyOfficialWebProviderError("Tavily timed out") from exc
        except httpx.RequestError as exc:
            raise Stage9TavilyOfficialWebProviderError(
                "Tavily could not be reached"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise Stage9TavilyOfficialWebProviderError(
                f"Tavily returned HTTP {exc.response.status_code}"
            ) from exc
        except (ValueError, ValidationError) as exc:
            raise Stage9TavilyOfficialWebProviderError(
                "Tavily returned an invalid response envelope"
            ) from exc

        if len(envelope.results) > maximum_results:
            raise Stage9TavilyOfficialWebProviderError(
                "Tavily exceeded the requested result boundary"
            )
        retrieved_at = self._clock().isoformat()
        documents: list[Stage9OfficialWebDocument] = []
        for result in envelope.results:
            content = result.raw_content
            if content is None or not content.strip():
                raise Stage9TavilyOfficialWebProviderError(
                    "Tavily result did not include exact raw content"
                )
            if len(content.encode("utf-8")) > _MAXIMUM_DOCUMENT_BYTES:
                raise Stage9TavilyOfficialWebProviderError(
                    "Tavily raw content exceeded the byte boundary"
                )
            self._validate_url(result.url, allowed_domains)
            documents.append(
                Stage9OfficialWebDocument(
                    url=result.url,
                    title=result.title,
                    content=content,
                    retrieved_at=retrieved_at,
                    response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
        return tuple(documents)

    @staticmethod
    def _validate_url(url: str, allowed_domains: tuple[str, ...]) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        allowed = tuple(value.casefold().strip(".") for value in allowed_domains)
        if parsed.scheme != "https" or not any(
            host == domain or host.endswith(f".{domain}") for domain in allowed
        ):
            raise Stage9TavilyOfficialWebProviderError(
                "Tavily result URL was outside the allowlist"
            )

    def _post(self, payload: dict[str, object]) -> httpx.Response:
        kwargs = {
            "headers": {"Authorization": f"Bearer {self._api_key}"},
            "json": payload,
            "timeout": self._timeout_seconds,
        }
        if self._client is not None:
            return self._client.post(f"{self._base_url}/search", **kwargs)
        with httpx.Client() as client:
            return client.post(f"{self._base_url}/search", **kwargs)
