"""Provider-neutral contracts for grounded patent technical concepts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.patent_research_request import PatentResearchRequest

MAXIMUM_PATENT_TECHNICAL_CONCEPTS = 2
MAXIMUM_PATENT_TECHNICAL_TERMS_PER_CONCEPT = 4
MAXIMUM_PATENT_TECHNICAL_TERM_CHARACTERS = 80


class PatentTechnicalConceptRole(StrEnum):
    """Planning role of one grounded technical concept group."""

    PRIMARY = "primary"
    ALTERNATE = "alternate"


class PatentTechnicalConcept(BaseModel):
    """One bounded group of technical terms copied from the user request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    role: PatentTechnicalConceptRole
    terms: tuple[str, ...] = Field(
        min_length=1,
        max_length=MAXIMUM_PATENT_TECHNICAL_TERMS_PER_CONCEPT,
    )

    @model_validator(mode="after")
    def validate_terms(self) -> Self:
        """Require bounded, clean, nonduplicate technical terms."""

        normalized: list[str] = []

        for term in self.terms:
            if term != term.strip():
                raise ValueError(
                    "patent technical terms must not contain outer whitespace"
                )
            if not term:
                raise ValueError("patent technical terms must not be blank")
            if len(term) > MAXIMUM_PATENT_TECHNICAL_TERM_CHARACTERS:
                raise ValueError("patent technical term is too long")
            if any(ord(character) < 32 or ord(character) == 127 for character in term):
                raise ValueError(
                    "patent technical terms must not contain control characters"
                )
            normalized.append(term.casefold())

        if len(set(normalized)) != len(normalized):
            raise ValueError("patent technical terms must be unique within one concept")

        return self

    def duplicate_key(self) -> tuple[str, ...]:
        """Return a conservative case-insensitive concept identity."""

        return tuple(sorted(term.casefold() for term in self.terms))


class PatentTechnicalConceptSelection(BaseModel):
    """Structured model output before request-grounding validation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    concepts: tuple[PatentTechnicalConcept, ...] = Field(
        min_length=1,
        max_length=MAXIMUM_PATENT_TECHNICAL_CONCEPTS,
    )

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        """Require PRIMARY first, optional ALTERNATE second, and no duplicates."""

        if self.concepts[0].role is not PatentTechnicalConceptRole.PRIMARY:
            raise ValueError("first patent technical concept must be primary")

        if (
            len(self.concepts) == 2
            and self.concepts[1].role is not PatentTechnicalConceptRole.ALTERNATE
        ):
            raise ValueError("second patent technical concept must be alternate")

        keys = [concept.duplicate_key() for concept in self.concepts]
        if len(set(keys)) != len(keys):
            raise ValueError("patent technical concepts must not be duplicates")

        return self


class PatentTechnicalConceptPlan(BaseModel):
    """Request-bound grounded technical concept plan."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: PatentResearchRequest
    concepts: tuple[PatentTechnicalConcept, ...] = Field(
        min_length=1,
        max_length=MAXIMUM_PATENT_TECHNICAL_CONCEPTS,
    )

    @model_validator(mode="after")
    def validate_grounding(self) -> Self:
        """Require every selected term to occur in the original request text."""

        PatentTechnicalConceptSelection(concepts=self.concepts)

        request_text = (f"{self.request.question}\n{self.request.objective}").casefold()

        for concept in self.concepts:
            for term in concept.terms:
                if term.casefold() not in request_text:
                    raise ValueError(
                        "patent technical term must be grounded in "
                        "question or objective"
                    )

        return self
