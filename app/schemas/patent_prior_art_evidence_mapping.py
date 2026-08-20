"""Provider-neutral contracts for claim-element to prior-art evidence mapping."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence_relevance_judgment import EvidenceRelevanceJudgment


class PatentPriorArtEvidenceEvaluation(BaseModel):
    """One technical-relevance evaluation for an exact prior-art excerpt."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    evidence_id: str
    source_id: str
    document_id: str
    excerpt: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=1)
    judgment: EvidenceRelevanceJudgment

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        required = {
            "publication_number": self.publication_number,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "excerpt": self.excerpt,
        }
        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")

        if self.end_character <= self.start_character:
            raise ValueError("end_character must be greater than start_character")
        return self


class PatentClaimElementEvidenceMapping(BaseModel):
    """One claim element with ordered prior-art evidence evaluations."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    element_number: int = Field(ge=1)
    element_text: str
    evaluations: tuple[PatentPriorArtEvidenceEvaluation, ...] = ()

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        if self.element_text != self.element_text.strip():
            raise ValueError("element_text must not contain outer whitespace")
        if not self.element_text:
            raise ValueError("element_text must not be blank")

        evidence_ids = tuple(
            evaluation.evidence_id.strip().casefold() for evaluation in self.evaluations
        )
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "evidence evaluations must have unique evidence IDs per element"
            )
        return self


class PatentClaimEvidenceMapping(BaseModel):
    """One source claim bound to ordered element/evidence mappings."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    original_claim_text: str
    elements: tuple[PatentClaimElementEvidenceMapping, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.original_claim_text != self.original_claim_text.strip():
            raise ValueError("original_claim_text must not contain outer whitespace")
        if not self.original_claim_text:
            raise ValueError("original_claim_text must not be blank")

        numbers = tuple(element.element_number for element in self.elements)
        if numbers != tuple(range(1, len(self.elements) + 1)):
            raise ValueError("claim element mapping numbers must be contiguous from 1")
        return self


class PatentClaimSetEvidenceMapping(BaseModel):
    """One language-specific claim set with prior-art evidence mappings."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[PatentClaimEvidenceMapping, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("language must not be blank")

        claim_numbers = tuple(claim.claim_number for claim in self.claims)
        if len(set(claim_numbers)) != len(claim_numbers):
            raise ValueError("claim numbers must be unique within one mapped claim set")

        positions = tuple(claim.provider_position for claim in self.claims)
        if positions != tuple(range(1, len(self.claims) + 1)):
            raise ValueError("mapped claim provider positions must be contiguous")
        return self


class PatentClaimsDocumentEvidenceMapping(BaseModel):
    """Claim-element evidence mappings bound to one exact target publication."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    source_endpoint: str
    claim_sets: tuple[PatentClaimSetEvidenceMapping, ...] = Field(min_length=1)

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
