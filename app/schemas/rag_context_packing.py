"""Typed contracts for bounded whole-chunk RAG context packing."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.retrieval_result import RetrievalResult


class RagContextOmissionReason(StrEnum):
    """Explicit ceiling that prevented one whole chunk from being packed."""

    ITEM_LIMIT = "item_limit"
    UTF8_BYTE_LIMIT = "utf8_byte_limit"
    ESTIMATED_TOKEN_LIMIT = "estimated_token_limit"


class RagContextPackingBudget(BaseModel):
    """Independent ceilings for one rendered evidence context."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_items: int = Field(ge=1, le=100)
    maximum_utf8_bytes: int = Field(ge=1, le=10_000_000)
    maximum_estimated_tokens: int = Field(ge=1, le=1_000_000)
    token_estimator_id: str = Field(min_length=1, max_length=200)

    @field_validator("token_estimator_id")
    @classmethod
    def validate_estimator_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("token_estimator_id must not be blank")
        if value != value.strip():
            raise ValueError("token_estimator_id must not have surrounding whitespace")
        return value


class RagContextPackingRequest(BaseModel):
    """Ordered relevant retrievals and the context packing budget."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    candidates: list[RetrievalResult] = Field(default_factory=list, max_length=100)
    budget: RagContextPackingBudget

    @model_validator(mode="after")
    def validate_candidates(self) -> Self:
        identities = [item.chunk.chunk_id.casefold() for item in self.candidates]
        if len(set(identities)) != len(identities):
            raise ValueError("context packing candidate chunk IDs must be unique")
        ranks = [item.rank for item in self.candidates]
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise ValueError("context packing candidate ranks must be contiguous")
        return self


class PackedRagContextItem(BaseModel):
    """One exact input retrieval accepted as a complete evidence chunk."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    retrieval: RetrievalResult
    original_position: int = Field(ge=1)
    packed_rank: int = Field(ge=1)
    incremental_utf8_bytes: int = Field(ge=1)
    incremental_estimated_tokens: int = Field(ge=0)


class OmittedRagContextItem(BaseModel):
    """One exact input retrieval omitted with all applicable ceiling reasons."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    retrieval: RetrievalResult
    original_position: int = Field(ge=1)
    reasons: list[RagContextOmissionReason] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_reasons(self) -> Self:
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("context omission reasons must be unique")
        expected = sorted(self.reasons, key=list(RagContextOmissionReason).index)
        if self.reasons != expected:
            raise ValueError("context omission reasons must use canonical order")
        return self


class RagContextPackingUsage(BaseModel):
    """Observed packed context size and classification counts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    candidate_count: int = Field(ge=0)
    included_count: int = Field(ge=0)
    omitted_count: int = Field(ge=0)
    context_utf8_bytes: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)


class RagContextPackingResult(BaseModel):
    """Complete, auditable classification of every ordered candidate."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: RagContextPackingRequest
    included: list[PackedRagContextItem] = Field(default_factory=list)
    omitted: list[OmittedRagContextItem] = Field(default_factory=list)
    usage: RagContextPackingUsage
    was_truncated: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        candidates = self.request.candidates
        classified = [
            *((item.original_position, item.retrieval) for item in self.included),
            *((item.original_position, item.retrieval) for item in self.omitted),
        ]
        positions = [position for position, _ in classified]
        if len(set(positions)) != len(positions):
            raise ValueError("each context candidate must be classified exactly once")
        if sorted(positions) != list(range(1, len(candidates) + 1)):
            raise ValueError("included and omitted items must cover every candidate")
        for position, retrieval in classified:
            if retrieval != candidates[position - 1]:
                raise ValueError("classified item must preserve the exact candidate")

        included_positions = [item.original_position for item in self.included]
        if included_positions != sorted(included_positions):
            raise ValueError("included items must preserve candidate order")
        omitted_positions = [item.original_position for item in self.omitted]
        if omitted_positions != sorted(omitted_positions):
            raise ValueError("omitted items must preserve candidate order")
        packed_ranks = [item.packed_rank for item in self.included]
        if packed_ranks != list(range(1, len(self.included) + 1)):
            raise ValueError("packed ranks must be contiguous from one")

        expected_usage = RagContextPackingUsage(
            candidate_count=len(candidates),
            included_count=len(self.included),
            omitted_count=len(self.omitted),
            context_utf8_bytes=sum(
                item.incremental_utf8_bytes for item in self.included
            ),
            estimated_tokens=sum(
                item.incremental_estimated_tokens for item in self.included
            ),
        )
        if self.usage != expected_usage:
            raise ValueError("context packing usage must match classified items")
        budget = self.request.budget
        if self.usage.included_count > budget.maximum_items:
            raise ValueError("included context items exceed budget")
        if self.usage.context_utf8_bytes > budget.maximum_utf8_bytes:
            raise ValueError("packed UTF-8 bytes exceed budget")
        if self.usage.estimated_tokens > budget.maximum_estimated_tokens:
            raise ValueError("packed estimated tokens exceed budget")
        if self.was_truncated != bool(self.omitted):
            raise ValueError("was_truncated must reflect omitted candidates")
        return self
