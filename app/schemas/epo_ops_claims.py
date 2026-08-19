"""Provider-level contracts for EPO OPS patent claim retrieval."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EpoOpsClaimText(BaseModel):
    """One raw claim-text item in provider order.

    ``position`` is only the 1-based order observed inside one language-specific
    claims container. It is not yet a parsed legal claim number.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    position: int = Field(ge=1)
    text: str

    @model_validator(mode="after")
    def validate_claim_text(self) -> Self:
        if not self.text.strip():
            raise ValueError("text must not be blank")
        return self


class EpoOpsClaimSet(BaseModel):
    """One language-specific provider claim set."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    language: str
    claims: tuple[EpoOpsClaimText, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        if not self.language.strip():
            raise ValueError("language must not be blank")
        expected = tuple(range(1, len(self.claims) + 1))
        actual = tuple(claim.position for claim in self.claims)
        if actual != expected:
            raise ValueError("claim positions must be contiguous provider order")
        return self


class EpoOpsClaimsRecord(BaseModel):
    """Raw provider claims bound to one exact DOCDB publication identity."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    source_endpoint: str
    claim_sets: tuple[EpoOpsClaimSet, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        for field_name, value in {
            "publication_number": self.publication_number,
            "publication_docdb": self.publication_docdb,
            "source_endpoint": self.source_endpoint,
        }.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        return self
