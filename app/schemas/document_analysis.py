"""Structured output schema for AIRA document analysis."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

FindingTitle = Annotated[str, Field(min_length=1, max_length=120)]
FindingEvidence = Annotated[str, Field(min_length=1, max_length=500)]
RecommendedAction = Annotated[str, Field(min_length=1, max_length=300)]


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DocumentFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: FindingTitle
    evidence: FindingEvidence
    severity: FindingSeverity

    @field_validator("title", "evidence")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        return normalized


class DocumentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    key_findings: list[DocumentFinding] = Field(
        min_length=1,
        max_length=10,
    )
    recommended_actions: list[RecommendedAction] = Field(
        max_length=10,
    )
    needs_human_review: StrictBool

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must not be empty")
        return normalized

    @field_validator("recommended_actions")
    @classmethod
    def normalize_recommended_actions(
        cls,
        value: list[str],
    ) -> list[str]:
        normalized_actions: list[str] = []
        seen_actions: set[str] = set()

        for action in value:
            normalized = action.strip()
            if not normalized:
                raise ValueError(
                    "recommended action must not be empty"
                )

            action_key = normalized.casefold()
            if action_key in seen_actions:
                raise ValueError(
                    "recommended actions must not contain duplicates"
                )

            seen_actions.add(action_key)
            normalized_actions.append(normalized)

        return normalized_actions
