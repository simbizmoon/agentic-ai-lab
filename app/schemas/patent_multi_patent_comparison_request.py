"""Bounded user request contract for one patent comparison workflow."""

from __future__ import annotations

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig

_CLAIM_LANGUAGE_PATTERN = re.compile(r"[A-Z]{2}", re.ASCII)
_EXACT_EPO_PUBLICATION_PATTERN = re.compile(r"EP[0-9]+[A-Z][0-9]?", re.ASCII)


class PatentMultiPatentComparisonRequest(BaseModel):
    """Describe an explicit, cost-bounded technical comparison request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    target_publication_number: str
    comparison_publication_numbers: tuple[str, ...] = Field(
        min_length=2,
        max_length=4,
    )
    claim_language: str = "EN"
    claim_number: int = Field(default=1, ge=1)
    maximum_claim_elements: int = Field(default=1, ge=1, le=8)
    maximum_mapping_calls: int = Field(default=2, ge=1, le=32)
    maximum_bytes: int = HttpHtmlReaderConfig().maximum_bytes

    @field_validator("target_publication_number")
    @classmethod
    def normalize_target_publication_number(cls, value: str) -> str:
        normalized = normalize_patent_publication_number(value)
        if _EXACT_EPO_PUBLICATION_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "exact EPO comparison requires an EP publication with kind code, "
                "for example EP1000000B1"
            )
        return normalized

    @field_validator("comparison_publication_numbers")
    @classmethod
    def normalize_comparison_publication_numbers(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(
            normalize_patent_publication_number(value) for value in values
        )
        if any(
            _EXACT_EPO_PUBLICATION_PATTERN.fullmatch(value) is None
            for value in normalized
        ):
            raise ValueError(
                "exact EPO comparison requires EP publications with kind codes, "
                "for example EP1000000A1"
            )
        folded = tuple(value.casefold() for value in normalized)
        if len(set(folded)) != len(folded):
            raise ValueError("comparison publication numbers must be unique")
        return normalized

    @field_validator("claim_language")
    @classmethod
    def normalize_claim_language(cls, value: str) -> str:
        normalized = value.strip().upper()
        if _CLAIM_LANGUAGE_PATTERN.fullmatch(normalized) is None:
            raise ValueError("claim_language must be a two-letter ASCII language code")
        return normalized

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Enforce the shared byte policy and worst-case mapping-call budget."""

        HttpHtmlReaderConfig(maximum_bytes=self.maximum_bytes)
        if self.planned_maximum_mapping_calls > self.maximum_mapping_calls:
            raise ValueError(
                "planned element/evidence pairs exceed maximum_mapping_calls"
            )
        return self

    @property
    def planned_maximum_mapping_calls(self) -> int:
        """Return the explicit worst-case Step 4D evaluator-call count."""

        return self.maximum_claim_elements * len(self.comparison_publication_numbers)
