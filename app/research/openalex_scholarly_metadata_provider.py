"""Bounded OpenAlex scholarly metadata provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from hashlib import sha256
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.research.scholarly_identifier_normalizer import (
    ScholarlyIdentifierNormalizationError,
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import (
    ScholarlyProviderError,
    ScholarlyProviderUsage,
    ScholarlyRecordFailure,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyAuthor,
    ScholarlyIdentifier,
    ScholarlyIdentifierType,
    ScholarlyIntegrityStatus,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


class _OpenAlexAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    id: str | None = None
    display_name: str
    orcid: str | None = None


class _OpenAlexInstitution(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    display_name: str


class _OpenAlexAuthorship(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    author: _OpenAlexAuthor
    institutions: list[_OpenAlexInstitution] = Field(default_factory=list)


class _OpenAlexSource(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    display_name: str | None = None


class _OpenAlexLocation(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    landing_page_url: str | None = None
    pdf_url: str | None = None
    is_oa: bool | None = None
    license: str | None = None
    source: _OpenAlexSource | None = None


class _OpenAlexOpenAccess(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    is_oa: bool | None = None


class _OpenAlexWork(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    id: str
    doi: str | None = None
    title: str | None = None
    display_name: str | None = None
    publication_date: str | None = None
    publication_year: int | None = None
    type: str | None = None
    language: str | None = None
    authorships: list[_OpenAlexAuthorship] = Field(default_factory=list)
    primary_location: _OpenAlexLocation | None = None
    best_oa_location: _OpenAlexLocation | None = None
    open_access: _OpenAlexOpenAccess | None = None
    abstract_inverted_index: dict[str, list[int]] | None = None


class _OpenAlexMeta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    count: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    cost_usd: float | int | None = None


class _OpenAlexResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    meta: _OpenAlexMeta
    results: list[dict[str, Any]] = Field(default_factory=list)


class OpenAlexScholarlyMetadataProvider(ScholarlyMetadataProvider):
    """Normalize one-page OpenAlex work searches into AIRA contracts."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://api.openalex.org",
        timeout_seconds: float = 30.0,
        api_key: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if api_key is not None and not api_key.strip():
            raise ValueError("api_key must not be blank when provided")
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._clock = clock

    @property
    def name(self) -> str:
        return "openalex"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        started = perf_counter()
        params: dict[str, str | int] = {
            "search": request.query.strip(),
            "per_page": request.maximum_results,
            "page": 1,
        }
        filters: list[str] = []
        if request.start_date is not None:
            filters.append(f"from_publication_date:{request.start_date.isoformat()}")
        if request.end_date is not None:
            filters.append(f"to_publication_date:{request.end_date.isoformat()}")
        if filters:
            params["filter"] = ",".join(filters)
        if self._api_key is not None:
            params["api_key"] = self._api_key

        try:
            response = self._get(params)
            response.raise_for_status()
            envelope = _OpenAlexResponse.model_validate(response.json())
        except httpx.TimeoutException:
            return self._failed(
                request, started, "ProviderTimeout", "OpenAlex timed out.", True
            )
        except httpx.RequestError:
            return self._failed(
                request,
                started,
                "ProviderNetworkError",
                "OpenAlex could not be reached.",
                True,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            return self._failed(
                request,
                started,
                "ProviderHttpError",
                f"OpenAlex returned HTTP {status}.",
                status == 429 or status >= 500,
                http_status=status,
            )
        except (ValueError, ValidationError):
            return self._failed(
                request,
                started,
                "ResponseValidationError",
                "OpenAlex returned an invalid response envelope.",
                False,
            )

        response_digest = sha256(response.content).hexdigest()
        retrieved_at = self._clock().isoformat()
        works: list[ScholarlyWork] = []
        failures: list[ScholarlyRecordFailure] = []
        for position, raw in enumerate(envelope.results, start=1):
            try:
                parsed = _OpenAlexWork.model_validate(raw)
                work = self._normalize_work(
                    parsed,
                    request_url=str(response.request.url),
                    retrieved_at=retrieved_at,
                    response_sha256=response_digest,
                )
                if request.require_abstract and work.abstract is None:
                    raise ValueError("required abstract is absent")
                if request.work_types and work.work_type not in request.work_types:
                    raise ValueError("work type is outside the requested types")
                works.append(work)
            except (
                ValueError,
                ValidationError,
                ScholarlyIdentifierNormalizationError,
            ) as exc:
                failures.append(
                    ScholarlyRecordFailure(
                        provider_position=position,
                        provider_record_id=self._raw_record_id(raw),
                        error_type="RecordValidationError",
                        message=str(exc),
                    )
                )

        usage = ScholarlyProviderUsage(
            request_count=1,
            records_received=len(envelope.results),
            records_accepted=len(works),
            records_rejected=len(failures),
            duration_ms=(perf_counter() - started) * 1000,
        )
        if works and failures:
            status = ScholarlySearchStatus.PARTIAL
        elif works:
            status = ScholarlySearchStatus.SUCCEEDED
        elif failures:
            return ScholarlySearchResult(
                request=request,
                provider=self.name,
                status=ScholarlySearchStatus.FAILED,
                error=ScholarlyProviderError(
                    error_type="AllRecordsRejected",
                    message="All OpenAlex records failed validation.",
                ),
                record_failures=tuple(failures),
                usage=usage,
            )
        else:
            status = ScholarlySearchStatus.NO_RESULTS
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=status,
            works=tuple(works),
            record_failures=tuple(failures),
            usage=usage,
            metadata={
                "provider_total_count": str(envelope.meta.count),
                "provider_cost_usd": str(envelope.meta.cost_usd or 0),
            },
        )

    def _get(self, params: dict[str, str | int]) -> httpx.Response:
        url = f"{self._base_url}/works"
        if self._client is not None:
            return self._client.get(url, params=params, timeout=self._timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, params=params, timeout=self._timeout_seconds)

    def _normalize_work(
        self,
        value: _OpenAlexWork,
        *,
        request_url: str,
        retrieved_at: str,
        response_sha256: str,
    ) -> ScholarlyWork:
        openalex_id = normalize_scholarly_identifier(
            ScholarlyIdentifierType.OPENALEX, value.id
        )
        identifiers: list[ScholarlyIdentifier] = [openalex_id]
        if value.doi is not None:
            identifiers.append(
                normalize_scholarly_identifier(ScholarlyIdentifierType.DOI, value.doi)
            )
        title = value.title or value.display_name
        if title is None:
            raise ValueError("title is absent")
        location = value.best_oa_location or value.primary_location
        landing_url = (
            location.landing_page_url if location is not None else None
        ) or value.id
        pdf_url = location.pdf_url if location is not None else None
        is_oa = (
            location.is_oa
            if location is not None and location.is_oa is not None
            else value.open_access.is_oa
            if value.open_access is not None
            else None
        )
        state = (
            ScholarlyAccessState.OPEN
            if is_oa is True and pdf_url is not None
            else ScholarlyAccessState.METADATA_ONLY
        )
        abstract_text = self._abstract_text(value.abstract_inverted_index)
        record_id = openalex_id.normalized_value
        abstract = (
            ScholarlyAbstract(
                text=abstract_text,
                language=value.language,
                provider=self.name,
                provider_record_id=record_id,
                source_url=request_url,
            )
            if abstract_text is not None
            else None
        )
        return ScholarlyWork(
            work_id=f"openalex-{record_id}",
            title=title,
            work_type=self._work_type(value.type),
            version_type=(
                ScholarlyVersionType.PREPRINT
                if value.type == "preprint"
                else ScholarlyVersionType.UNKNOWN
            ),
            identifiers=tuple(identifiers),
            authors=tuple(
                ScholarlyAuthor(
                    display_name=item.author.display_name,
                    position=position,
                    orcid=self._orcid(item.author.orcid),
                    affiliations=tuple(
                        institution.display_name for institution in item.institutions
                    ),
                )
                for position, item in enumerate(value.authorships, start=1)
            ),
            publication_date=(
                date.fromisoformat(value.publication_date)
                if value.publication_date is not None
                else None
            ),
            publication_year=value.publication_year,
            venue=(
                location.source.display_name
                if location is not None and location.source is not None
                else None
            ),
            abstract=abstract,
            access=ScholarlyAccess(
                state=state,
                landing_page_url=landing_url,
                full_text_url=pdf_url if state is ScholarlyAccessState.OPEN else None,
                license=location.license if location is not None else None,
                is_open_access=is_oa,
            ),
            integrity_status=ScholarlyIntegrityStatus.UNKNOWN,
            provenance=ScholarlyProviderProvenance(
                provider=self.name,
                provider_record_id=record_id,
                request_url=request_url,
                retrieved_at=retrieved_at,
                response_sha256=response_sha256,
            ),
        )

    def _failed(
        self,
        request: ScholarlySearchRequest,
        started: float,
        error_type: str,
        message: str,
        retryable: bool,
        *,
        http_status: int | None = None,
    ) -> ScholarlySearchResult:
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=ScholarlySearchStatus.FAILED,
            error=ScholarlyProviderError(
                error_type=error_type,
                message=message,
                retryable=retryable,
                http_status=http_status,
            ),
            usage=ScholarlyProviderUsage(
                request_count=1,
                records_received=0,
                records_accepted=0,
                records_rejected=0,
                duration_ms=(perf_counter() - started) * 1000,
            ),
        )

    @staticmethod
    def _raw_record_id(raw: dict[str, Any]) -> str | None:
        value = raw.get("id")
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _abstract_text(index: dict[str, list[int]] | None) -> str | None:
        if not index:
            return None
        words: dict[int, str] = {}
        for word, positions in index.items():
            if not word.strip() or any(position < 0 for position in positions):
                raise ValueError("invalid abstract inverted index")
            for position in positions:
                if position in words:
                    raise ValueError("duplicate abstract word position")
                words[position] = word
        expected = list(range(len(words)))
        if sorted(words) != expected:
            raise ValueError("abstract positions must be contiguous")
        return " ".join(words[position] for position in expected)

    @staticmethod
    def _orcid(value: str | None) -> str | None:
        return value.rstrip("/").rsplit("/", 1)[-1] if value is not None else None

    @staticmethod
    def _work_type(value: str | None) -> ScholarlyWorkType:
        mapping = {
            "article": ScholarlyWorkType.JOURNAL_ARTICLE,
            "review": ScholarlyWorkType.JOURNAL_ARTICLE,
            "preprint": ScholarlyWorkType.PREPRINT,
            "book": ScholarlyWorkType.BOOK,
            "book-chapter": ScholarlyWorkType.BOOK_CHAPTER,
            "dissertation": ScholarlyWorkType.THESIS,
            "dataset": ScholarlyWorkType.DATASET,
            "report": ScholarlyWorkType.REPORT,
        }
        return mapping.get(value or "", ScholarlyWorkType.OTHER)
