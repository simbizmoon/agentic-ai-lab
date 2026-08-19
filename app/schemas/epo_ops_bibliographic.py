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


class EpoOpsCpcClassification(BaseModel):
    """One provider-level CPCI classification decomposition."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    section: str
    class_number: str
    subclass: str
    main_group: str
    subgroup: str
    sequence: str | None = None
    classification_value: str | None = None
    scheme_office: str | None = None
    generating_office: str | None = None

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        """Preserve provider CPCI components without reconstruction or inference."""

        required = {
            "section": self.section,
            "class_number": self.class_number,
            "subclass": self.subclass,
            "main_group": self.main_group,
            "subgroup": self.subgroup,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        optional = {
            "sequence": self.sequence,
            "classification_value": self.classification_value,
            "scheme_office": self.scheme_office,
            "generating_office": self.generating_office,
        }
        for name, value in optional.items():
            if value is not None and not value.strip():
                raise ValueError(f"{name} must not be blank when provided")
        return self


class EpoOpsIpcClassification(BaseModel):
    """One provider-level IPC classification representation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str
    sequence: str | None = None

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        """Preserve provider IPC text without parsing or legal inference."""

        if not self.text.strip():
            raise ValueError("text must not be blank")
        if self.sequence is not None and not self.sequence.strip():
            raise ValueError("sequence must not be blank when provided")
        return self


class EpoOpsPartyRepresentation(BaseModel):
    """One provider-supplied applicant or inventor name representation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str
    sequence: str | None = None
    data_format: str | None = None

    @model_validator(mode="after")
    def validate_representation(self) -> Self:
        """Preserve bounded provider text without merging party identities."""

        if not self.name.strip():
            raise ValueError("name must not be blank")
        for field_name, value in {
            "sequence": self.sequence,
            "data_format": self.data_format,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must not be blank when provided")
        return self


class EpoOpsPriorityClaim(BaseModel):
    """One provider-level EPODOC priority claim plus bounded provenance."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    priority_number: str
    priority_date: date | None = None
    sequence: str | None = None
    claim_kind: str | None = None
    original_number: str | None = None

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate provider-derived priority text without legal inference."""

        if not self.priority_number.strip():
            raise ValueError("priority_number must not be blank")
        for name, value in {
            "sequence": self.sequence,
            "claim_kind": self.claim_kind,
            "original_number": self.original_number,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(f"{name} must not be blank when provided")
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
    family_id: str | None = None
    title_language: str | None = None
    priority_claims: tuple[EpoOpsPriorityClaim, ...] = ()
    ipc_classifications: tuple[EpoOpsIpcClassification, ...] = ()
    cpc_classifications: tuple[EpoOpsCpcClassification, ...] = ()
    applicants: tuple[EpoOpsPartyRepresentation, ...] = ()
    inventors: tuple[EpoOpsPartyRepresentation, ...] = ()

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
        if self.family_id is not None and not self.family_id.strip():
            raise ValueError("family_id must not be blank")
        if self.title_language is not None and not self.title_language.strip():
            raise ValueError("title_language must not be blank")
        return self


class EpoOpsBibliographicSearchResult(BaseModel):
    """Immutable parsed records returned for one bounded OPS request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: EpoOpsSearchRequest
    records: tuple[EpoOpsBibliographicRecord, ...]
