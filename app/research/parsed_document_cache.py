"""Persistent cache contracts and identities for parsed local documents."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from importlib.metadata import PackageNotFoundError, version
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.report_integrity import is_valid_sha256_digest
from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.research_source_document import ResearchSourceContentType

PARSED_DOCUMENT_CACHE_SCHEMA_VERSION: Final = 1
ParsedDocumentCacheSchemaVersion = Literal[1]
TEXT_PARSER_ID: Final = "aira-text"
MARKDOWN_PARSER_ID: Final = "aira-markdown"
PDF_TEXT_PARSER_ID: Final = "aira-pdf-text"
HWPX_TEXT_PARSER_ID: Final = "aira-hwpx-text"
LOCAL_DOCUMENT_PARSER_REVISION: Final = 1

_CONFIGURATIONS: Final = {
    ".txt": "utf8-exact-v1",
    ".md": "utf8-exact-v1",
    ".pdf": "normalized-pages-double-newline-v1",
    ".hwpx": "spine-body-paragraphs-double-newline-v1",
}


class ParsedDocumentCacheError(RuntimeError):
    """Raised when parsed-document cache storage cannot be used safely."""


class ParsedDocumentCacheEntryTooLargeError(ParsedDocumentCacheError):
    """Raised when a parsed document cannot fit the configured entry bound."""


class ParsedDocumentParserIdentity(BaseModel):
    """Explicit, bumpable identity for one local parsing behavior."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    content_type: ResearchSourceContentType
    parser_id: str = Field(min_length=1)
    parser_revision: int = Field(ge=1)
    configuration_identity: str = Field(min_length=1)
    dependency_identity: str | None = None

    @field_validator("parser_id", "configuration_identity")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("parser identity values must not be blank")
        return value

    @field_validator("dependency_identity")
    @classmethod
    def validate_optional_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("dependency_identity must not be blank")
        return value


class ParsedDocumentCacheIdentity(BaseModel):
    """Content and parser identity used to address one parsed result."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: ParsedDocumentCacheSchemaVersion = (
        PARSED_DOCUMENT_CACHE_SCHEMA_VERSION
    )
    raw_content_sha256: str
    raw_file_size_bytes: int = Field(ge=0)
    parser: ParsedDocumentParserIdentity

    @field_validator("raw_content_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("raw_content_sha256 must be a lowercase SHA-256 digest")
        return value

    @field_validator("raw_file_size_bytes")
    @classmethod
    def reject_boolean_size(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("raw_file_size_bytes must be an integer")
        return value

    @property
    def cache_key(self) -> str:
        return build_parsed_document_cache_key(self)


class ParsedDocumentCacheEntry(BaseModel):
    """Strict versioned envelope for one cached parsed document."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: ParsedDocumentCacheSchemaVersion
    cache_key: str
    identity: ParsedDocumentCacheIdentity
    parsed_document: ParsedLocalDocument

    @field_validator("cache_key")
    @classmethod
    def validate_cache_key_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("cache_key must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_entry_identity(self) -> Self:
        if self.schema_version != self.identity.schema_version:
            raise ValueError("cache entry schema version does not match identity")
        if self.cache_key != self.identity.cache_key:
            raise ValueError("cache key does not match parsed-document identity")
        if self.parsed_document.content_type != self.identity.parser.content_type:
            raise ValueError("parsed content type does not match parser identity")
        return self


class ParsedDocumentCacheEntryAccess(ABC):
    """Operations for one identity while its exclusive cache lock is held."""

    @abstractmethod
    def get(self) -> ParsedLocalDocument | None:
        """Recheck the locked entry without acquiring another lock."""

    @abstractmethod
    def put(self, parsed_document: ParsedLocalDocument) -> None:
        """Persist the locked entry without acquiring another lock."""


class ParsedDocumentCache(ABC):
    """Persistent storage contract for path-neutral parsed documents."""

    @abstractmethod
    def get(self, identity: ParsedDocumentCacheIdentity) -> ParsedLocalDocument | None:
        """Return a deep-safe cached parsed document, or None on a miss."""

    @abstractmethod
    def put(
        self,
        identity: ParsedDocumentCacheIdentity,
        parsed_document: ParsedLocalDocument,
    ) -> None:
        """Persist a parsed document for an exact identity."""

    @abstractmethod
    def exclusive_entry(
        self, identity: ParsedDocumentCacheIdentity
    ) -> AbstractContextManager[ParsedDocumentCacheEntryAccess]:
        """Lock one identity for an atomic recheck, compute, and write flow."""


def build_parsed_document_cache_key(
    identity: ParsedDocumentCacheIdentity,
) -> str:
    """Hash an unambiguous canonical serialization of the full identity."""

    if not isinstance(identity, ParsedDocumentCacheIdentity):
        raise TypeError("identity must be a ParsedDocumentCacheIdentity")
    canonical = json.dumps(
        identity.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_local_document_parser_identity(
    suffix: str,
    *,
    pdf_dependency_identity: str | None = None,
) -> ParsedDocumentParserIdentity:
    """Build the explicit parser identity for one supported local suffix."""

    if not isinstance(suffix, str):
        raise TypeError("suffix must be a string")
    normalized = suffix.casefold()
    if normalized == ".markdown":
        normalized = ".md"
    definitions = {
        ".txt": (ResearchSourceContentType.TEXT, TEXT_PARSER_ID),
        ".md": (ResearchSourceContentType.MARKDOWN, MARKDOWN_PARSER_ID),
        ".pdf": (ResearchSourceContentType.PDF_TEXT, PDF_TEXT_PARSER_ID),
        ".hwpx": (ResearchSourceContentType.HWPX_TEXT, HWPX_TEXT_PARSER_ID),
    }
    if normalized not in definitions:
        raise ValueError("suffix does not identify a supported local document parser")
    content_type, parser_id = definitions[normalized]
    dependency_identity = None
    if normalized == ".pdf":
        dependency_identity = pdf_dependency_identity or _installed_pypdf_identity()
    return ParsedDocumentParserIdentity(
        content_type=content_type,
        parser_id=parser_id,
        parser_revision=LOCAL_DOCUMENT_PARSER_REVISION,
        configuration_identity=_CONFIGURATIONS[normalized],
        dependency_identity=dependency_identity,
    )


def identity_from_validated_source(
    source: LocalDocumentAccessResult,
) -> ParsedDocumentCacheIdentity:
    """Build path-neutral identity from one authoritative access result."""

    if not isinstance(source, LocalDocumentAccessResult):
        raise TypeError("source must be a LocalDocumentAccessResult")
    return ParsedDocumentCacheIdentity(
        raw_content_sha256=source.content_sha256,
        raw_file_size_bytes=source.file_size_bytes,
        parser=build_local_document_parser_identity(source.resolved_path.suffix),
    )


def _installed_pypdf_identity() -> str:
    try:
        dependency_version = version("pypdf")
    except PackageNotFoundError as error:
        raise RuntimeError("pypdf dependency identity is unavailable") from error
    return f"pypdf=={dependency_version}"
