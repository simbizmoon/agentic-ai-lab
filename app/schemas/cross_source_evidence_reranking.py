"""Typed contracts for bounded cross-source evidence reranking."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.hybrid_retrieval import (
    HybridRetrievalMatch,
    HybridRetrievalResponse,
)


class EvidenceRerankingEvaluationState(StrEnum):
    """Whether one hybrid candidate received a relevance judgment."""

    EVALUATED = "evaluated"
    UNEVALUATED = "unevaluated"


class EvidenceRerankingBudget(BaseModel):
    """Serializable execution ceiling for one reranking operation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_attempts: int = Field(ge=1, le=100)
    maximum_recorded_tokens: int = Field(ge=1, le=1_000_000)
    maximum_elapsed_seconds: float = Field(gt=0.0, le=3600.0)

    @field_validator("maximum_elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("maximum_elapsed_seconds must be finite")
        return value


class CrossSourceEvidenceRerankingRequest(BaseModel):
    """Question, objective, candidate bound, and execution budget."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    question: str
    objective: str
    maximum_candidates: int = Field(default=8, ge=1, le=50)
    budget: EvidenceRerankingBudget

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.question.strip():
            raise ValueError("reranking question must not be blank")
        if not self.objective.strip():
            raise ValueError("reranking objective must not be blank")
        return self


class EvidenceRerankingUsage(BaseModel):
    """Observed attempts, tokens, and elapsed time."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    attempts: int = Field(default=0, ge=0)
    recorded_tokens: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0.0)

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("elapsed_seconds must be finite")
        return value


class CrossSourceEvidenceRerankItem(BaseModel):
    """One exact hybrid candidate with optional semantic judgment."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    hybrid_match: HybridRetrievalMatch
    evaluation_state: EvidenceRerankingEvaluationState
    judgment: EvidenceRelevanceJudgment | None = None
    response_id: str | None = None
    request_id: str | None = None
    final_rank: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        if self.evaluation_state is EvidenceRerankingEvaluationState.EVALUATED:
            if self.judgment is None:
                raise ValueError("evaluated rerank item requires a judgment")
            if self.response_id is None or not self.response_id.strip():
                raise ValueError("evaluated rerank item requires response_id")
            if self.request_id is not None and not self.request_id.strip():
                raise ValueError("request_id must not be blank when provided")
        else:
            if self.judgment is not None:
                raise ValueError("unevaluated rerank item must not contain a judgment")
            if self.response_id is not None or self.request_id is not None:
                raise ValueError(
                    "unevaluated rerank item must not contain provider identity"
                )
        return self


class CrossSourceEvidenceRerankingResult(BaseModel):
    """Validated reranking output bound to one exact hybrid response."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: CrossSourceEvidenceRerankingRequest
    hybrid_response: HybridRetrievalResponse
    items: list[CrossSourceEvidenceRerankItem] = Field(default_factory=list)
    usage: EvidenceRerankingUsage = Field(default_factory=EvidenceRerankingUsage)
    budget_exhausted: bool = False
    candidate_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    unevaluated_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.candidate_count != len(self.hybrid_response.matches):
            raise ValueError("candidate_count must match hybrid response")
        if self.candidate_count > self.request.maximum_candidates:
            raise ValueError("candidate_count must not exceed maximum_candidates")
        if len(self.items) != self.candidate_count:
            raise ValueError("rerank items must cover every hybrid candidate")

        original = {
            item.retrieval.chunk.chunk_id.casefold(): item
            for item in self.hybrid_response.matches
        }
        item_ids = [
            item.hybrid_match.retrieval.chunk.chunk_id.casefold() for item in self.items
        ]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("rerank item chunk IDs must be unique")
        if set(item_ids) != set(original):
            raise ValueError("rerank items must preserve the hybrid candidate set")
        for item in self.items:
            identity = item.hybrid_match.retrieval.chunk.chunk_id.casefold()
            if item.hybrid_match != original[identity]:
                raise ValueError("rerank item must preserve exact hybrid match")

        expected_evaluated = sum(
            item.evaluation_state is EvidenceRerankingEvaluationState.EVALUATED
            for item in self.items
        )
        if self.evaluated_count != expected_evaluated:
            raise ValueError("evaluated_count must match rerank items")
        if self.unevaluated_count != self.candidate_count - expected_evaluated:
            raise ValueError("unevaluated_count must match rerank items")
        ranks = [item.final_rank for item in self.items]
        if ranks != list(range(1, len(self.items) + 1)):
            raise ValueError("final rerank positions must be contiguous from one")
        ordering = [self._sort_key(item) for item in self.items]
        if ordering != sorted(ordering):
            raise ValueError("rerank items violate deterministic relevance ordering")

        budget = self.request.budget
        exceeded = (
            self.usage.attempts > budget.maximum_attempts
            or self.usage.recorded_tokens > budget.maximum_recorded_tokens
            or self.usage.elapsed_seconds > budget.maximum_elapsed_seconds
        )
        if exceeded and not self.budget_exhausted:
            raise ValueError("over-budget usage must mark budget_exhausted")
        if self.unevaluated_count and not self.budget_exhausted:
            raise ValueError("unevaluated candidates require budget_exhausted")
        return self

    @staticmethod
    def _sort_key(
        item: CrossSourceEvidenceRerankItem,
    ) -> tuple[int | float | str, ...]:
        judgment = item.judgment
        if judgment is None:
            bucket = 2
            relevance_score = 0.0
        elif judgment.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT:
            bucket = 0
            relevance_score = judgment.relevance_score
        elif judgment.relevance_level is EvidenceRelevanceLevel.PARTIALLY_RELEVANT:
            bucket = 1
            relevance_score = judgment.relevance_score
        else:
            bucket = 3
            relevance_score = judgment.relevance_score
        return (
            bucket,
            -relevance_score,
            item.hybrid_match.retrieval.rank,
            item.hybrid_match.retrieval.chunk.chunk_id,
        )
