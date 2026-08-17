"""Internal contracts for bounded EPO OPS bibliographic search."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EpoOpsDocumentIdType(StrEnum):
    """OPS identity formats preserved by the first bibliographic parser."""

    DOCDB = "docdb"


class EpoOpsSearchRequest(BaseModel):
    """One bounded caller-supplied CQL search request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cql_query: str
    maximum_results: int = Field(default=8, ge=1, le=8)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Reject a query with no searchable CQL content."""

        if not self.cql_query.strip():
            raise ValueError("cql_query must not be blank")
        return self


class EpoOpsBibliographicRecord(BaseModel):
    """One parsed OPS bibliographic result, not verified product metadata."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    title: str
    publication_date: date | None
    source_endpoint: str
    document_id_type: EpoOpsDocumentIdType
    application_number: str | None = None
    title_language: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate required provider-derived text without inferring metadata."""

        if not self.publication_number.strip():
            raise ValueError("publication_number must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if not self.source_endpoint.strip():
            raise ValueError("source_endpoint must not be blank")
        if self.application_number is not None and not self.application_number.strip():
            raise ValueError("application_number must not be blank")
        if self.title_language is not None and not self.title_language.strip():
            raise ValueError("title_language must not be blank")
        return self


class EpoOpsBibliographicSearchResult(BaseModel):
    """Immutable parsed records returned for one bounded OPS request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: EpoOpsSearchRequest
    records: tuple[EpoOpsBibliographicRecord, ...]
