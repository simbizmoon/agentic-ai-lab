"""Normalized metadata contract for one patent publication record."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.research.patent_source_policy import (
    EPO_OPS_SOURCE_FAMILY,
    WIPO_PATENTSCOPE_SOURCE_FAMILY,
    source_family_for_url,
)


class PatentSourceFamily(StrEnum):
    """Patent source families accepted by the current product policy."""

    WIPO_PATENTSCOPE = WIPO_PATENTSCOPE_SOURCE_FAMILY
    EPO_OPS = EPO_OPS_SOURCE_FAMILY


class PatentMetadataVerificationState(StrEnum):
    """Whether present metadata passed a source-specific contract."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class PatentCpcClassification(BaseModel):
    """One provider-neutral decomposed CPC classification."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    section: str
    class_number: str
    subclass: str
    main_group: str
    subgroup: str

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        """Reject blank CPC components without reconstructing or inferring a symbol."""

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
        return self


class PatentIpcClassification(BaseModel):
    """One provider-neutral IPC classification text."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        """Reject blank text without parsing or classification inference."""

        if not self.text.strip():
            raise ValueError("text must not be blank")
        return self


class PatentParty(BaseModel):
    """One provider-neutral patent applicant or inventor display name."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str

    @model_validator(mode="after")
    def validate_party(self) -> Self:
        """Reject a blank display name without inferring legal identity."""

        if not self.name.strip():
            raise ValueError("name must not be blank")
        return self


class PatentPriorityClaim(BaseModel):
    """Provider-neutral priority metadata without legal-validity inference."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    priority_number: str
    priority_date: date | None = None

    @model_validator(mode="after")
    def validate_priority_claim(self) -> Self:
        """Reject blank provider-derived identity without inferring semantics."""

        if not self.priority_number.strip():
            raise ValueError("priority_number must not be blank")
        return self


class PatentSourceMetadata(BaseModel):
    """Represent normalized patent metadata, not a search candidate.

    VERIFIED means that every field actually present passed the accepted
    source-specific verification contract. It does not mean that every
    possible metadata field, including publication_date, is available.
    Step 1 intentionally provides no production adapter that emits VERIFIED.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_family: PatentSourceFamily
    publication_number: str
    title: str
    source_url: str
    metadata_verification_state: PatentMetadataVerificationState
    publication_date: date | None = None
    application_number: str | None = None
    priority_claims: tuple[PatentPriorityClaim, ...] = ()
    ipc_classifications: tuple[PatentIpcClassification, ...] = ()
    cpc_classifications: tuple[PatentCpcClassification, ...] = ()
    applicants: tuple[PatentParty, ...] = ()
    inventors: tuple[PatentParty, ...] = ()

    @field_validator("publication_number")
    @classmethod
    def normalize_publication_number(cls, value: str) -> str:
        """Store the conservative publication identity representation."""

        return normalize_patent_publication_number(value)

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        """Validate required text and bind the URL to its source family."""

        if not self.publication_number.strip():
            raise ValueError("publication_number must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if self.application_number is not None and not self.application_number.strip():
            raise ValueError("application_number must not be blank when provided")

        actual_family = source_family_for_url(self.source_url)
        if actual_family != self.source_family.value:
            raise ValueError("source_url does not match source_family")
        return self
