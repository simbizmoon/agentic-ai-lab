"""Verified two-step official-source discovery and exact-read contracts."""

from __future__ import annotations

from typing import Protocol, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebDocument,
)


class Stage9OfficialSourceCandidate(BaseModel):
    """One source URL discovered without treating snippets as evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    url: str
    title: str

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if not self.url.strip() or self.url != self.url.strip():
            raise ValueError("candidate URL must be normalized and nonblank")
        if not self.title.strip() or self.title != self.title.strip():
            raise ValueError("candidate title must be normalized and nonblank")
        return self


class Stage9VerifiedOfficialSourceBatch(BaseModel):
    """Exact official documents plus independently visible request accounting."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    documents: tuple[Stage9OfficialWebDocument, ...]
    discovered_candidates: int = Field(ge=0, le=2)
    rejected_candidates: int = Field(ge=0, le=2)
    discovery_provider_requests: int = Field(ge=0, le=1)
    exact_read_external_requests: int = Field(ge=0, le=2)
    total_external_requests: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        if self.rejected_candidates > self.discovered_candidates:
            raise ValueError("rejected candidates cannot exceed discoveries")
        if len(self.documents) > self.discovered_candidates:
            raise ValueError("documents cannot exceed discovered candidates")
        expected = self.discovery_provider_requests + self.exact_read_external_requests
        if self.total_external_requests != expected:
            raise ValueError("total external requests must equal observed components")
        if self.exact_read_external_requests < len(self.documents):
            raise ValueError("each exact document requires an observed read")
        return self


class Stage9OfficialSourceDiscovery(Protocol):
    """Discover candidate URLs; returned text is never accepted as evidence."""

    def discover(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> tuple[Stage9OfficialSourceCandidate, ...]: ...


class Stage9ExactOfficialDocumentReader(Protocol):
    """Read one already-validated official URL as an exact document."""

    def read(self, *, url: str) -> Stage9OfficialWebDocument: ...


class Stage9VerifiedOfficialSourceProviderError(RuntimeError):
    """Two-step discovery/read violated an identity or request boundary."""


class Stage9VerifiedOfficialSourceProvider:
    """Validate discovered URLs before any exact official-document read."""

    def __init__(
        self,
        *,
        discovery: Stage9OfficialSourceDiscovery,
        reader: Stage9ExactOfficialDocumentReader,
    ) -> None:
        self._discovery = discovery
        self._reader = reader

    def acquire(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> Stage9VerifiedOfficialSourceBatch:
        if not query.strip():
            raise ValueError("query must not be blank")
        if not allowed_domains or any(not item.strip() for item in allowed_domains):
            raise ValueError("allowed_domains must contain normalized domains")
        if maximum_results < 1 or maximum_results > 2:
            raise ValueError("maximum_results must be between 1 and 2")

        candidates = self._discovery.discover(
            query=query,
            allowed_domains=allowed_domains,
            maximum_results=maximum_results,
        )
        if not isinstance(candidates, tuple):
            raise Stage9VerifiedOfficialSourceProviderError(
                "discovery must return a tuple"
            )
        if len(candidates) > maximum_results:
            raise Stage9VerifiedOfficialSourceProviderError(
                "discovery exceeded the result boundary"
            )

        documents: list[Stage9OfficialWebDocument] = []
        rejected = 0
        reads = 0
        seen_urls: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, Stage9OfficialSourceCandidate):
                raise Stage9VerifiedOfficialSourceProviderError(
                    "discovery returned an invalid candidate"
                )
            normalized_url = candidate.url.casefold()
            if normalized_url in seen_urls or not self._is_allowed(
                candidate.url, allowed_domains
            ):
                rejected += 1
                continue
            seen_urls.add(normalized_url)
            reads += 1
            document = self._reader.read(url=candidate.url)
            if not isinstance(document, Stage9OfficialWebDocument):
                raise Stage9VerifiedOfficialSourceProviderError(
                    "reader returned an invalid document"
                )
            if not self._is_allowed(document.url, allowed_domains):
                raise Stage9VerifiedOfficialSourceProviderError(
                    "reader crossed the official-domain boundary"
                )
            documents.append(document)

        return Stage9VerifiedOfficialSourceBatch(
            documents=tuple(documents),
            discovered_candidates=len(candidates),
            rejected_candidates=rejected,
            discovery_provider_requests=1,
            exact_read_external_requests=reads,
            total_external_requests=1 + reads,
        )

    @staticmethod
    def _is_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        return parsed.scheme == "https" and any(
            host == domain.casefold() or host.endswith(f".{domain.casefold()}")
            for domain in allowed_domains
        )
