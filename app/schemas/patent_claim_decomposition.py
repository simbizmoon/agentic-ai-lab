"""Provider-neutral contracts for semantic patent claim-element decomposition."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PatentClaimElement(BaseModel):
    """One ordered technical element extracted from a patent claim."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    element_number: int = Field(ge=1)
    text: str

    @model_validator(mode="after")
    def validate_element(self) -> Self:
        if self.text != self.text.strip():
            raise ValueError("claim element text must not contain outer whitespace")
        if not self.text:
            raise ValueError("claim element text must not be blank")
        if any(ord(character) < 32 or ord(character) == 127 for character in self.text):
            raise ValueError("claim element text must not contain control characters")
        return self


class PatentClaimElementSelection(BaseModel):
    """Structured model output before binding elements to one source claim."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    elements: tuple[PatentClaimElement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        numbers = tuple(element.element_number for element in self.elements)
        if numbers != tuple(range(1, len(self.elements) + 1)):
            raise ValueError("claim element numbers must be contiguous from 1")

        normalized = tuple(element.text.casefold() for element in self.elements)
        if len(set(normalized)) != len(normalized):
            raise ValueError("claim element texts must be unique")
        return self


class PatentClaimDecomposition(BaseModel):
    """One source patent claim bound to its ordered technical elements."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_number: int = Field(ge=1)
    provider_position: int = Field(ge=1)
    original_claim_text: str
    elements: tuple[PatentClaimElement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decomposition(self) -> Self:
        if self.original_claim_text != self.original_claim_text.strip():
            raise ValueError("original claim text must not contain outer whitespace")
        if not self.original_claim_text:
            raise ValueError("original claim text must not be blank")
        if any(
            ord(character) < 32 or ord(character) == 127
            for character in self.original_claim_text
        ):
            raise ValueError("original claim text must not contain control characters")

        PatentClaimElementSelection(elements=self.elements)
        return self


class PatentClaimSetDecomposition(BaseModel):
    """One language-specific patent claim set with ordered decompositions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[PatentClaimDecomposition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("claim decomposition language must not be blank")

        numbers = tuple(claim.claim_number for claim in self.claims)
        if len(set(numbers)) != len(numbers):
            raise ValueError(
                "claim numbers must be unique within one decomposition claim set"
            )

        positions = tuple(claim.provider_position for claim in self.claims)
        if positions != tuple(range(1, len(self.claims) + 1)):
            raise ValueError(
                "claim decomposition provider positions must be contiguous"
            )
        return self


class PatentClaimsDocumentDecomposition(BaseModel):
    """Decomposed multilingual claims bound to one exact publication identity."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    source_endpoint: str
    claim_sets: tuple[PatentClaimSetDecomposition, ...] = Field(min_length=1)

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
