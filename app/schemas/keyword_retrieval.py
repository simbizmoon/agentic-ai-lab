"""Schemas for deterministic keyword retrieval over document chunks."""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.retrieval_result import RetrievalResult


class KeywordRetrievalRequest(BaseModel):
    """Bounded inputs for one keyword retrieval operation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    minimum_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("minimum_score", mode="before")
    @classmethod
    def validate_finite_minimum_score(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("minimum_score must be finite")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.query.strip():
            raise ValueError("keyword retrieval query must not be blank")
        if not math.isfinite(self.minimum_score):
            raise ValueError("minimum_score must be finite")
        return self


class KeywordRetrievalExplanation(BaseModel):
    """Auditable lexical signals used to score one chunk."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    query_tokens: list[str] = Field(min_length=1)
    matched_terms: list[str] = Field(default_factory=list)
    token_coverage: float = Field(ge=0.0, le=1.0)
    exact_phrase_match: bool

    @model_validator(mode="after")
    def validate_explanation(self) -> Self:
        normalized_query = self._validate_unique_tokens(
            self.query_tokens,
            name="query_tokens",
        )
        normalized_matches = self._validate_unique_tokens(
            self.matched_terms,
            name="matched_terms",
        )
        if not set(normalized_matches).issubset(normalized_query):
            raise ValueError("matched_terms must be a subset of query_tokens")
        expected_coverage = len(normalized_matches) / len(normalized_query)
        if not math.isclose(
            self.token_coverage,
            expected_coverage,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "token_coverage must equal matched query tokens divided by query tokens"
            )
        return self

    @staticmethod
    def _validate_unique_tokens(values: list[str], *, name: str) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if not value.strip():
                raise ValueError(f"{name} must not contain blank values")
            normalized.append(value.strip().casefold())
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{name} must not contain duplicates")
        return normalized


class KeywordRetrievalMatch(BaseModel):
    """One standard retrieval result with lexical score evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    retrieval: RetrievalResult
    explanation: KeywordRetrievalExplanation

    @model_validator(mode="after")
    def validate_match(self) -> Self:
        if self.retrieval.score < 0.0:
            raise ValueError("keyword retrieval score must not be negative")
        if not self.explanation.matched_terms:
            raise ValueError("keyword retrieval match must contain a matched term")
        return self


class KeywordRetrievalResponse(BaseModel):
    """Validated, deterministically ordered keyword retrieval output."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: KeywordRetrievalRequest
    corpus_chunk_count: int = Field(ge=0)
    matches: list[KeywordRetrievalMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if len(self.matches) > self.request.top_k:
            raise ValueError("matches must not exceed request top_k")
        if len(self.matches) > self.corpus_chunk_count:
            raise ValueError("matches must not exceed corpus_chunk_count")

        chunk_ids = [
            item.retrieval.chunk.chunk_id.strip().casefold() for item in self.matches
        ]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("matched chunk IDs must be unique")

        ranks = [item.retrieval.rank for item in self.matches]
        if ranks != list(range(1, len(self.matches) + 1)):
            raise ValueError("match ranks must be contiguous from one")

        for item in self.matches:
            if item.retrieval.score < self.request.minimum_score:
                raise ValueError("match score must satisfy request minimum_score")

        ordering = [
            (-item.retrieval.score, item.retrieval.chunk.chunk_id)
            for item in self.matches
        ]
        if ordering != sorted(ordering):
            raise ValueError(
                "matches must be ordered by descending score then chunk_id"
            )
        return self
