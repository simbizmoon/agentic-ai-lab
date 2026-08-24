"""Typed contracts for deterministic rank-only hybrid retrieval fusion."""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.retrieval_result import RetrievalResult


class HybridRetrievalRequest(BaseModel):
    """Bounded configuration for one deterministic fusion operation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    top_k: int = Field(default=5, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=1000)


class HybridRetrievalMatch(BaseModel):
    """One fused result with independently auditable channel evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    retrieval: RetrievalResult
    rrf_k: int = Field(ge=1, le=1000)
    keyword_rank: int | None = Field(default=None, ge=1)
    keyword_score: float | None = Field(default=None, ge=0.0, le=1.0)
    keyword_contribution: float | None = Field(default=None, gt=0.0, le=0.5)
    semantic_rank: int | None = Field(default=None, ge=1)
    semantic_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    semantic_contribution: float | None = Field(default=None, gt=0.0, le=0.5)
    fused_score: float = Field(gt=0.0, le=1.0)
    matched_channel_count: int = Field(ge=1, le=2)

    @field_validator(
        "keyword_score",
        "keyword_contribution",
        "semantic_score",
        "semantic_contribution",
        "fused_score",
        mode="before",
    )
    @classmethod
    def validate_finite_numbers(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("hybrid retrieval numeric values must be finite")
        return value

    @model_validator(mode="after")
    def validate_match(self) -> Self:
        keyword_present = self._validate_channel(
            name="keyword",
            rank=self.keyword_rank,
            score=self.keyword_score,
            contribution=self.keyword_contribution,
        )
        semantic_present = self._validate_channel(
            name="semantic",
            rank=self.semantic_rank,
            score=self.semantic_score,
            contribution=self.semantic_contribution,
        )
        expected_count = int(keyword_present) + int(semantic_present)
        if self.matched_channel_count != expected_count:
            raise ValueError(
                "matched_channel_count must equal the present retrieval channels"
            )
        expected_fused_score = sum(
            value
            for value in (
                self.keyword_contribution,
                self.semantic_contribution,
            )
            if value is not None
        )
        if not math.isclose(
            self.fused_score,
            expected_fused_score,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("fused_score must equal the channel contributions")
        if not math.isclose(
            self.retrieval.score,
            self.fused_score,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("retrieval score must equal fused_score")
        return self

    def _validate_channel(
        self,
        *,
        name: str,
        rank: int | None,
        score: float | None,
        contribution: float | None,
    ) -> bool:
        values = (rank, score, contribution)
        present_count = sum(value is not None for value in values)
        if present_count not in (0, 3):
            raise ValueError(
                f"{name} rank, score, and contribution must be present together"
            )
        if present_count == 0:
            return False
        assert rank is not None and contribution is not None
        expected = 1.0 / (self.rrf_k + rank)
        if not math.isclose(
            contribution,
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"{name}_contribution must equal reciprocal rank contribution"
            )
        return True


class HybridRetrievalResponse(BaseModel):
    """Validated and deterministically ordered hybrid retrieval output."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: HybridRetrievalRequest
    keyword_result_count: int = Field(ge=0)
    semantic_result_count: int = Field(ge=0)
    unique_chunk_count: int = Field(ge=0)
    matches: list[HybridRetrievalMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.unique_chunk_count > (
            self.keyword_result_count + self.semantic_result_count
        ):
            raise ValueError("unique_chunk_count must not exceed channel result counts")
        if self.unique_chunk_count < max(
            self.keyword_result_count,
            self.semantic_result_count,
        ):
            raise ValueError("unique_chunk_count must cover each channel result count")
        if len(self.matches) > self.request.top_k:
            raise ValueError("matches must not exceed request top_k")
        if len(self.matches) > self.unique_chunk_count:
            raise ValueError("matches must not exceed unique_chunk_count")

        normalized_ids = [
            item.retrieval.chunk.chunk_id.strip().casefold() for item in self.matches
        ]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("hybrid matched chunk IDs must be unique")
        ranks = [item.retrieval.rank for item in self.matches]
        if ranks != list(range(1, len(self.matches) + 1)):
            raise ValueError("hybrid match ranks must be contiguous from one")
        if any(item.rrf_k != self.request.rrf_k for item in self.matches):
            raise ValueError("match rrf_k must equal request rrf_k")
        ordering = [
            (-item.fused_score, item.retrieval.chunk.chunk_id) for item in self.matches
        ]
        if ordering != sorted(ordering):
            raise ValueError("matches must be ordered by fused score then chunk_id")
        return self
