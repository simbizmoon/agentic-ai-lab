"""Provider-neutral multi-patent technical comparison contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)


class PatentPriorArtPublicationComparison(BaseModel):
    """One prior-art publication cell containing exact technical evaluations."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    evaluations: tuple[PatentPriorArtEvidenceEvaluation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        if not self.publication_number.strip():
            raise ValueError("publication_number must not be blank")

        for evaluation in self.evaluations:
            if evaluation.publication_number != self.publication_number:
                raise ValueError(
                    "comparison evaluation publication_number must match its cell"
                )

        evidence_ids = tuple(
            evaluation.evidence_id.strip().casefold() for evaluation in self.evaluations
        )
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "comparison evaluations must have unique evidence IDs per publication"
            )
        return self


class PatentMultiPatentComparisonRow(BaseModel):
    """One ordered claim-element row grouped by prior-art publication."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    row_number: int = Field(ge=1)
    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    element_number: int = Field(ge=1)
    element_text: str
    publications: tuple[PatentPriorArtPublicationComparison, ...] = ()

    @model_validator(mode="after")
    def validate_row(self) -> Self:
        if self.element_text != self.element_text.strip():
            raise ValueError("element_text must not contain outer whitespace")
        if not self.element_text:
            raise ValueError("element_text must not be blank")

        publication_numbers = tuple(
            item.publication_number.strip().casefold() for item in self.publications
        )
        if len(set(publication_numbers)) != len(publication_numbers):
            raise ValueError(
                "prior-art publication numbers must be unique within one row"
            )
        return self


class PatentMultiPatentComparisonClaim(BaseModel):
    """One target claim represented as ordered multi-patent comparison rows."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    original_claim_text: str
    rows: tuple[PatentMultiPatentComparisonRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.original_claim_text != self.original_claim_text.strip():
            raise ValueError("original_claim_text must not contain outer whitespace")
        if not self.original_claim_text:
            raise ValueError("original_claim_text must not be blank")

        element_numbers = tuple(row.element_number for row in self.rows)
        if element_numbers != tuple(range(1, len(self.rows) + 1)):
            raise ValueError(
                "multi-patent comparison element numbers must be contiguous from 1"
            )

        for row in self.rows:
            if row.claim_number != self.claim_number:
                raise ValueError(
                    "multi-patent comparison row claim_number must match its claim"
                )
            if row.provider_position != self.provider_position:
                raise ValueError(
                    "multi-patent comparison row provider_position must match its claim"
                )
        return self


class PatentMultiPatentComparisonClaimSet(BaseModel):
    """One language-specific target claim set in provider order."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[PatentMultiPatentComparisonClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("language must not be blank")

        claim_numbers = tuple(claim.claim_number for claim in self.claims)
        if len(set(claim_numbers)) != len(claim_numbers):
            raise ValueError(
                "claim numbers must be unique within one comparison claim set"
            )

        positions = tuple(claim.provider_position for claim in self.claims)
        if positions != tuple(range(1, len(self.claims) + 1)):
            raise ValueError("comparison claim provider positions must be contiguous")
        return self


class PatentMultiPatentComparison(BaseModel):
    """Technical comparison of one target patent against multiple publications."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    target_publication_number: str
    target_publication_docdb: str
    target_source_endpoint: str
    prior_art_publications: tuple[str, ...]
    claim_sets: tuple[PatentMultiPatentComparisonClaimSet, ...] = Field(min_length=1)
    scope_notice: str

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        required = {
            "target_publication_number": self.target_publication_number,
            "target_publication_docdb": self.target_publication_docdb,
            "target_source_endpoint": self.target_source_endpoint,
            "scope_notice": self.scope_notice,
        }
        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")

        normalized_axis = tuple(
            publication.strip().casefold()
            for publication in self.prior_art_publications
        )
        if any(not publication for publication in normalized_axis):
            raise ValueError("prior_art_publications must not contain blanks")
        if len(set(normalized_axis)) != len(normalized_axis):
            raise ValueError("prior_art_publications must be unique")

        rows = tuple(
            row
            for claim_set in self.claim_sets
            for claim in claim_set.claims
            for row in claim.rows
        )
        row_numbers = tuple(row.row_number for row in rows)
        if row_numbers != tuple(range(1, len(row_numbers) + 1)):
            raise ValueError(
                "multi-patent comparison row numbers must be contiguous from 1"
            )

        encountered: list[str] = []
        for row in rows:
            row_publications = tuple(
                item.publication_number for item in row.publications
            )
            expected_row_order = tuple(
                publication
                for publication in self.prior_art_publications
                if publication in row_publications
            )
            if row_publications != expected_row_order:
                raise ValueError(
                    "row publication order must follow prior_art_publications"
                )

            for publication in row_publications:
                if publication not in encountered:
                    encountered.append(publication)

        if tuple(encountered) != self.prior_art_publications:
            raise ValueError(
                "prior_art_publications must match first-seen row publications"
            )

        return self
