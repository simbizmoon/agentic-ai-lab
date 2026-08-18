"""Schemas for bounded patent technical synthesis."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PATENT_ZERO_FINDING_OVERALL_SUMMARY = (
    "No semantically evaluated relevant finding was available."
)


class PatentTechnicalFindingSummary(BaseModel):
    """One bounded human-readable summary for an existing patent finding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    finding_id: str
    technical_summary: str

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if not self.finding_id.strip():
            raise ValueError("finding_id must not be blank")
        if not self.technical_summary.strip():
            raise ValueError("technical_summary must not be blank")
        return self


class PatentTechnicalSynthesis(BaseModel):
    """Bounded synthesis over existing patent technical findings only."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    overall_summary: str
    finding_summaries: list[PatentTechnicalFindingSummary] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_synthesis(self) -> Self:
        if not self.overall_summary.strip():
            raise ValueError("overall_summary must not be blank")

        finding_ids = [
            item.finding_id.strip().casefold() for item in self.finding_summaries
        ]
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("finding summary IDs must be unique")

        cleaned_limitations = [limitation.strip() for limitation in self.limitations]
        if any(not value for value in cleaned_limitations):
            raise ValueError("limitations must not contain blank values")

        folded = [value.casefold() for value in cleaned_limitations]
        if len(set(folded)) != len(folded):
            raise ValueError("limitations must not contain duplicates")

        return self
