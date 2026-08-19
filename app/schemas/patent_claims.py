"""Provider-neutral parsed patent-claim contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PatentClaim(BaseModel):
    """One parsed patent claim without dependency or legal interpretation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    text: str

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if not self.text.strip():
            raise ValueError("text must not be blank")
        return self


class PatentClaimSet(BaseModel):
    """One language-specific parsed patent claim set."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[PatentClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("language must not be blank")

        numbers = tuple(claim.claim_number for claim in self.claims)
        if len(set(numbers)) != len(numbers):
            raise ValueError("claim numbers must be unique within one claim set")

        positions = tuple(claim.provider_position for claim in self.claims)
        if positions != tuple(range(1, len(self.claims) + 1)):
            raise ValueError("provider positions must be contiguous")
        return self


class PatentClaimsDocument(BaseModel):
    """Parsed multilingual patent claims bound to one exact publication identity."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    source_endpoint: str
    claim_sets: tuple[PatentClaimSet, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        for field_name, value in {
            "publication_number": self.publication_number,
            "publication_docdb": self.publication_docdb,
            "source_endpoint": self.source_endpoint,
        }.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        return self
