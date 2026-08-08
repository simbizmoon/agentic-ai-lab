"""Schemas for evidence relevance evaluation datasets."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceLevel,
)


class EvidenceRelevanceEvaluationCase(BaseModel):
    """One labeled evidence relevance evaluation case."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    case_id: str
    question: str
    objective: str
    evidence: str
    expected_level: EvidenceRelevanceLevel
    notes: str

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        """Validate required text."""

        for name in (
            "case_id",
            "question",
            "objective",
            "evidence",
            "notes",
        ):
            value = getattr(self, name)
            if not value.strip():
                raise ValueError(f"{name} must not be blank")

        return self


class EvidenceRelevanceEvaluationDataset(BaseModel):
    """Fixed labeled evidence relevance evaluation dataset."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    dataset_id: str
    cases: list[EvidenceRelevanceEvaluationCase] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Validate dataset identity and case uniqueness."""

        if not self.dataset_id.strip():
            raise ValueError("dataset_id must not be blank")

        case_ids = [
            case.case_id.strip().casefold()
            for case in self.cases
        ]

        if len(set(case_ids)) != len(case_ids):
            raise ValueError("case IDs must be unique")

        return self
