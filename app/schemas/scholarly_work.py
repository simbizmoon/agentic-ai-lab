"""Provider-neutral scholarly work identity and access schemas."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScholarlyIdentifierType(StrEnum):
    """Supported external scholarly identifier namespaces."""

    DOI = "doi"
    ARXIV = "arxiv"
    PMID = "pmid"
    PMCID = "pmcid"
    OPENALEX = "openalex"
    PROVIDER = "provider"
    OTHER = "other"


class ScholarlyWorkType(StrEnum):
    """Broad, provider-neutral scholarly work types."""

    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    PREPRINT = "preprint"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    THESIS = "thesis"
    DATASET = "dataset"
    REPORT = "report"
    OTHER = "other"


class ScholarlyVersionType(StrEnum):
    """Known manuscript or publication version."""

    SUBMITTED = "submitted"
    PREPRINT = "preprint"
    ACCEPTED_MANUSCRIPT = "accepted_manuscript"
    VERSION_OF_RECORD = "version_of_record"
    UPDATED_VERSION = "updated_version"
    UNKNOWN = "unknown"


class ScholarlyAccessState(StrEnum):
    """Observed access state without inferring permission."""

    OPEN = "open"
    RESTRICTED = "restricted"
    METADATA_ONLY = "metadata_only"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ScholarlyIntegrityStatus(StrEnum):
    """Provider-reported publication integrity status."""

    ACTIVE = "active"
    CORRECTED = "corrected"
    RETRACTED = "retracted"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


def _validate_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_optional_text(name: str, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{name} must not be blank when provided")


def _validate_http_url(name: str, value: str | None) -> None:
    if value is None:
        return
    _validate_text(name, value)
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL")


class ScholarlyIdentifier(BaseModel):
    """One exact identifier as supplied and normalized by a provider adapter."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    identifier_type: ScholarlyIdentifierType
    value: str
    normalized_value: str
    provider: str | None = None

    @model_validator(mode="after")
    def validate_identifier(self) -> Self:
        _validate_text("value", self.value)
        _validate_text("normalized_value", self.normalized_value)
        _validate_optional_text("provider", self.provider)
        if self.identifier_type is ScholarlyIdentifierType.PROVIDER:
            if self.provider is None:
                raise ValueError("provider identifier requires provider")
        elif self.provider is not None:
            raise ValueError("provider is only valid for provider identifiers")
        return self


class ScholarlyAuthor(BaseModel):
    """One ordered author with only provider-supplied identity fields."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    display_name: str
    position: int = Field(ge=1)
    given_name: str | None = None
    family_name: str | None = None
    orcid: str | None = None
    affiliations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_author(self) -> Self:
        _validate_text("display_name", self.display_name)
        _validate_optional_text("given_name", self.given_name)
        _validate_optional_text("family_name", self.family_name)
        _validate_optional_text("orcid", self.orcid)
        if any(not value.strip() for value in self.affiliations):
            raise ValueError("affiliations must not contain blank values")
        normalized = [value.strip().casefold() for value in self.affiliations]
        if len(set(normalized)) != len(normalized):
            raise ValueError("affiliations must not contain duplicates")
        return self


class ScholarlyAbstract(BaseModel):
    """An abstract bound to the exact provider record that supplied it."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str
    language: str | None = None
    provider: str
    provider_record_id: str
    source_url: str

    @model_validator(mode="after")
    def validate_abstract(self) -> Self:
        _validate_text("text", self.text)
        _validate_optional_text("language", self.language)
        _validate_text("provider", self.provider)
        _validate_text("provider_record_id", self.provider_record_id)
        _validate_http_url("source_url", self.source_url)
        return self


class ScholarlyAccess(BaseModel):
    """Observed landing-page and full-text access facts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    state: ScholarlyAccessState
    landing_page_url: str
    full_text_url: str | None = None
    license: str | None = None
    is_open_access: bool | None = None

    @model_validator(mode="after")
    def validate_access(self) -> Self:
        _validate_http_url("landing_page_url", self.landing_page_url)
        _validate_http_url("full_text_url", self.full_text_url)
        _validate_optional_text("license", self.license)
        if self.state is ScholarlyAccessState.OPEN:
            if self.is_open_access is not True:
                raise ValueError("open access state requires is_open_access=True")
            if self.full_text_url is None:
                raise ValueError("open access state requires full_text_url")
        if (
            self.state is ScholarlyAccessState.METADATA_ONLY
            and self.full_text_url is not None
        ):
            raise ValueError("metadata-only access must not include full_text_url")
        return self


class ScholarlyProviderProvenance(BaseModel):
    """Exact binding to one provider response record."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider: str
    provider_record_id: str
    request_url: str
    retrieved_at: str
    response_sha256: str

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        _validate_text("provider", self.provider)
        _validate_text("provider_record_id", self.provider_record_id)
        _validate_http_url("request_url", self.request_url)
        _validate_text("retrieved_at", self.retrieved_at)
        digest = self.response_sha256.strip().casefold()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("response_sha256 must be a 64-character hex digest")
        return self


class ScholarlyWork(BaseModel):
    """One normalized scholarly work without fabricated metadata."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    work_id: str
    title: str
    work_type: ScholarlyWorkType
    version_type: ScholarlyVersionType
    identifiers: tuple[ScholarlyIdentifier, ...]
    authors: tuple[ScholarlyAuthor, ...] = ()
    publication_date: date | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    venue: str | None = None
    publisher: str | None = None
    abstract: ScholarlyAbstract | None = None
    access: ScholarlyAccess
    integrity_status: ScholarlyIntegrityStatus = ScholarlyIntegrityStatus.UNKNOWN
    related_work_ids: tuple[str, ...] = ()
    provenance: ScholarlyProviderProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_work(self) -> Self:
        _validate_text("work_id", self.work_id)
        _validate_text("title", self.title)
        _validate_optional_text("venue", self.venue)
        _validate_optional_text("publisher", self.publisher)
        if not self.identifiers:
            raise ValueError("identifiers must contain at least one identifier")
        identifier_keys = [
            (item.identifier_type, item.normalized_value.strip().casefold())
            for item in self.identifiers
        ]
        if len(set(identifier_keys)) != len(identifier_keys):
            raise ValueError("identifiers must not contain duplicates")
        positions = [author.position for author in self.authors]
        if positions != list(range(1, len(positions) + 1)):
            raise ValueError("author positions must be contiguous and ordered from 1")
        if (
            self.publication_date is not None
            and self.publication_year is not None
            and self.publication_date.year != self.publication_year
        ):
            raise ValueError("publication_year must match publication_date")
        related = [value.strip().casefold() for value in self.related_work_ids]
        if any(not value for value in related):
            raise ValueError("related_work_ids must not contain blank values")
        if len(set(related)) != len(related):
            raise ValueError("related_work_ids must not contain duplicates")
        if self.work_id.strip().casefold() in related:
            raise ValueError("related_work_ids must not contain work_id")
        for key, value in self.metadata.items():
            if not key.strip() or not value.strip():
                raise ValueError("metadata keys and values must not be blank")
        providers = {self.provenance.provider.strip().casefold()}
        if self.abstract is not None:
            if self.abstract.provider.strip().casefold() not in providers:
                raise ValueError("abstract provider must match provenance provider")
            if self.abstract.provider_record_id != self.provenance.provider_record_id:
                raise ValueError("abstract record must match provenance record")
        return self
