"""Contracts for bounded explicit patent-search query candidates."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.patent_research_request import PatentResearchRequest

MAXIMUM_PATENT_CQL_LENGTH = 512
MAXIMUM_PATENT_QUERY_CANDIDATES = 2


class PatentSearchQueryPurpose(StrEnum):
    """Role of one explicit CQL candidate in the first patent slice."""

    PRIMARY = "primary"
    ALTERNATE = "alternate"


class PatentSearchQuery(BaseModel):
    """One explicit bounded CQL candidate without hidden query inference."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cql_query: str = Field(max_length=MAXIMUM_PATENT_CQL_LENGTH)
    purpose: PatentSearchQueryPurpose

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Reject blank or control-character-bearing CQL."""

        if not self.cql_query.strip():
            raise ValueError("cql_query must not be blank")

        if any(
            ord(character) < 32 or ord(character) == 127 for character in self.cql_query
        ):
            raise ValueError("cql_query must not contain control characters")

        return self

    def duplicate_key(self) -> str:
        """Return a conservative key for exact candidate deduplication."""

        return self.cql_query.strip()


class PatentSearchQueryPlan(BaseModel):
    """Validated bounded patent-query candidates for one patent request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: PatentResearchRequest
    queries: tuple[PatentSearchQuery, ...] = Field(
        min_length=1,
        max_length=MAXIMUM_PATENT_QUERY_CANDIDATES,
    )

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        """Validate deterministic purpose ordering and exact deduplication."""

        if self.queries[0].purpose is not PatentSearchQueryPurpose.PRIMARY:
            raise ValueError("first patent search query must be primary")

        if (
            len(self.queries) == 2
            and self.queries[1].purpose is not PatentSearchQueryPurpose.ALTERNATE
        ):
            raise ValueError("second patent search query must be alternate")

        duplicate_keys = [query.duplicate_key() for query in self.queries]
        if len(set(duplicate_keys)) != len(duplicate_keys):
            raise ValueError("patent search queries must not contain exact duplicates")

        return self
