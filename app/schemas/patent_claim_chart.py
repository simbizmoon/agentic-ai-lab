"""Provider-neutral structured claim-chart contracts for technical review."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)


class PatentClaimChartRow(BaseModel):
    """One ordered claim-element row with traceable technical evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    row_number: int = Field(ge=1)
    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    element_number: int = Field(ge=1)
    element_text: str
    evaluations: tuple[PatentPriorArtEvidenceEvaluation, ...] = ()

    @model_validator(mode="after")
    def validate_row(self) -> Self:
        if self.element_text != self.element_text.strip():
            raise ValueError("element_text must not contain outer whitespace")
        if not self.element_text:
            raise ValueError("element_text must not be blank")
        return self


class PatentClaimChartClaim(BaseModel):
    """One source claim represented as ordered chart rows."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    original_claim_text: str
    rows: tuple[PatentClaimChartRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.original_claim_text != self.original_claim_text.strip():
            raise ValueError("original_claim_text must not contain outer whitespace")
        if not self.original_claim_text:
            raise ValueError("original_claim_text must not be blank")

        element_numbers = tuple(row.element_number for row in self.rows)
        if element_numbers != tuple(range(1, len(self.rows) + 1)):
            raise ValueError("claim-chart element numbers must be contiguous from 1")

        for row in self.rows:
            if row.claim_number != self.claim_number:
                raise ValueError("claim-chart row claim_number must match its claim")
            if row.provider_position != self.provider_position:
                raise ValueError(
                    "claim-chart row provider_position must match its claim"
                )
        return self


class PatentClaimChartClaimSet(BaseModel):
    """One language-specific claim chart preserving provider order."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[PatentClaimChartClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("language must not be blank")

        claim_numbers = tuple(claim.claim_number for claim in self.claims)
        if len(set(claim_numbers)) != len(claim_numbers):
            raise ValueError("claim numbers must be unique within one claim chart set")

        positions = tuple(claim.provider_position for claim in self.claims)
        if positions != tuple(range(1, len(self.claims) + 1)):
            raise ValueError("claim-chart provider positions must be contiguous")
        return self


class PatentClaimChart(BaseModel):
    """Human-reviewable technical claim chart for one exact target publication."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    target_publication_number: str
    target_publication_docdb: str
    target_source_endpoint: str
    claim_sets: tuple[PatentClaimChartClaimSet, ...] = Field(min_length=1)
    scope_notice: str

    @model_validator(mode="after")
    def validate_chart(self) -> Self:
        required = {
            "target_publication_number": self.target_publication_number,
            "target_publication_docdb": self.target_publication_docdb,
            "target_source_endpoint": self.target_source_endpoint,
            "scope_notice": self.scope_notice,
        }
        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")

        row_numbers = tuple(
            row.row_number
            for claim_set in self.claim_sets
            for claim in claim_set.claims
            for row in claim.rows
        )
        if row_numbers != tuple(range(1, len(row_numbers) + 1)):
            raise ValueError("claim-chart row numbers must be contiguous from 1")
        return self
