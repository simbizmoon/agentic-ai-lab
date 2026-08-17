"""Deterministic planning of explicit bounded patent CQL candidates."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    MAXIMUM_PATENT_QUERY_CANDIDATES,
    PatentSearchQuery,
    PatentSearchQueryPlan,
    PatentSearchQueryPurpose,
)


class PatentSearchQueryPlanner:
    """Package caller-supplied CQL candidates without semantic inference."""

    def plan(
        self,
        *,
        request: PatentResearchRequest,
        cql_queries: Sequence[str],
    ) -> PatentSearchQueryPlan:
        """Return one validated primary/alternate candidate plan."""

        if isinstance(cql_queries, str):
            raise TypeError("cql_queries must be a sequence of CQL strings")

        if not cql_queries:
            raise ValueError("at least one patent CQL query is required")

        if len(cql_queries) > MAXIMUM_PATENT_QUERY_CANDIDATES:
            raise ValueError(
                "patent query planning supports at most two CQL candidates"
            )

        purposes = (
            PatentSearchQueryPurpose.PRIMARY,
            PatentSearchQueryPurpose.ALTERNATE,
        )

        queries = tuple(
            PatentSearchQuery(
                cql_query=cql_query,
                purpose=purposes[position],
            )
            for position, cql_query in enumerate(cql_queries)
        )

        return PatentSearchQueryPlan(
            request=request,
            queries=queries,
        )
