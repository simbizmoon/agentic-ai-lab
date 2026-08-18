"""Bounded execution of validated patent search-query plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPlan,
    PatentSearchQueryPurpose,
)


class PatentResearchHandlerProtocol(Protocol):
    """Minimal explicit-CQL patent handler contract used by the executor."""

    def run(
        self,
        request: PatentResearchRequest,
        *,
        cql_query: str,
    ) -> PatentResearchCollectionResult:
        """Execute one bounded explicit patent query."""


@dataclass(frozen=True)
class PatentResearchPlanExecutionResult:
    """One bounded query-plan execution and the query that produced it."""

    query: PatentSearchQuery
    collection: PatentResearchCollectionResult
    attempted_queries: tuple[PatentSearchQuery, ...]


class PatentResearchPlanExecutor:
    """Execute PRIMARY and optionally one zero-result ALTERNATE query."""

    def __init__(
        self,
        *,
        handler: PatentResearchHandlerProtocol,
    ) -> None:
        self._handler = handler

    def execute(
        self,
        plan: PatentSearchQueryPlan,
    ) -> PatentResearchPlanExecutionResult:
        """Execute one validated patent query plan conservatively.

        PRIMARY always executes first. ALTERNATE executes only when PRIMARY
        completes successfully with zero verified records. Provider, transport,
        parsing, identity, or selected-candidate failures are not converted into
        fallback and propagate unchanged.
        """

        attempted: list[PatentSearchQuery] = []
        primary = plan.queries[0]
        primary_collection = self._execute_query(
            request=plan.request,
            query=primary,
            attempted=attempted,
        )
        if primary_collection.verified_records:
            return PatentResearchPlanExecutionResult(
                query=primary,
                collection=primary_collection,
                attempted_queries=tuple(attempted),
            )

        if len(plan.queries) == 1:
            return PatentResearchPlanExecutionResult(
                query=primary,
                collection=primary_collection,
                attempted_queries=tuple(attempted),
            )

        alternate = plan.queries[1]
        if alternate.purpose is not PatentSearchQueryPurpose.ALTERNATE:
            raise RuntimeError("second patent query was not an alternate")

        alternate_collection = self._execute_query(
            request=plan.request,
            query=alternate,
            attempted=attempted,
        )
        return PatentResearchPlanExecutionResult(
            query=alternate,
            collection=alternate_collection,
            attempted_queries=tuple(attempted),
        )

    def _execute_query(
        self,
        *,
        request: PatentResearchRequest,
        query: PatentSearchQuery,
        attempted: list[PatentSearchQuery],
    ) -> PatentResearchCollectionResult:
        attempted.append(query)
        collection = self._handler.run(
            request,
            cql_query=query.cql_query,
        )
        if collection.request != request:
            raise RuntimeError(
                "patent handler result was not bound to the query-plan request"
            )
        return collection
