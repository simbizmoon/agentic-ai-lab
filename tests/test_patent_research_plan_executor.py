"""Tests for bounded patent query-plan execution policy."""

from __future__ import annotations

from datetime import date

import pytest

from app.research.epo_ops_patent_source_adapter import (
    build_verified_epo_patent_record,
)
from app.research.patent_research_plan_executor import PatentResearchPlanExecutor
from app.schemas.epo_ops_abstract import (
    EpoOpsAbstractRecord,
    EpoOpsVerifiedPatentRecord,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPlan,
    PatentSearchQueryPurpose,
)


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="Which seat occupancy patents are technically relevant?",
        objective="Collect bounded verified patent sources for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=1,
    )


def query_plan(*, include_alternate: bool = True) -> PatentSearchQueryPlan:
    queries = [
        PatentSearchQuery(
            cql_query='ta all "seat occupancy"',
            purpose=PatentSearchQueryPurpose.PRIMARY,
        )
    ]
    if include_alternate:
        queries.append(
            PatentSearchQuery(
                cql_query='ta all "pressure sensor"',
                purpose=PatentSearchQueryPurpose.ALTERNATE,
            )
        )
    return PatentSearchQueryPlan(
        request=request(),
        queries=tuple(queries),
    )


def bibliographic(number: str) -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number=number,
        publication_docdb=f"EP.{number[2:-2]}.A1",
        title="Seat occupancy detector",
        publication_date=date(2024, 1, 1),
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=test"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )


def collection_for(
    *,
    source_request: PatentResearchRequest,
    cql_query: str,
    with_record: bool,
) -> PatentResearchCollectionResult:
    search_request = EpoOpsSearchRequest(
        cql_query=cql_query,
        maximum_results=source_request.maximum_search_results,
    )
    records: tuple[EpoOpsBibliographicRecord, ...] = ()
    verified: tuple[EpoOpsVerifiedPatentRecord, ...] = ()

    if with_record:
        record = bibliographic("EP123456A1")
        abstract = EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text="A pressure sensor detects seat occupancy.",
            abstract_language="en",
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/docdb/{record.publication_docdb}/abstract"
            ),
        )
        records = (record,)
        verified = (
            build_verified_epo_patent_record(
                bibliographic=record,
                abstract=abstract,
            ),
        )

    return PatentResearchCollectionResult(
        request=source_request,
        search_result=EpoOpsBibliographicSearchResult(
            request=search_request,
            records=records,
        ),
        verified_records=verified,
    )


class FakeHandler:
    def __init__(
        self,
        *,
        records_by_query: dict[str, bool] | None = None,
        error_by_query: dict[str, Exception] | None = None,
        mismatched_request: bool = False,
    ) -> None:
        self.records_by_query = records_by_query or {}
        self.error_by_query = error_by_query or {}
        self.mismatched_request = mismatched_request
        self.calls: list[str] = []

    def run(
        self,
        source_request: PatentResearchRequest,
        *,
        cql_query: str,
    ) -> PatentResearchCollectionResult:
        self.calls.append(cql_query)
        error = self.error_by_query.get(cql_query)
        if error is not None:
            raise error

        result_request = (
            source_request.model_copy(
                update={"objective": "mismatched objective"},
            )
            if self.mismatched_request
            else source_request
        )
        return collection_for(
            source_request=result_request,
            cql_query=cql_query,
            with_record=self.records_by_query.get(cql_query, False),
        )


def test_executor_runs_primary_only_when_primary_has_results() -> None:
    plan = query_plan()
    primary = plan.queries[0]
    handler = FakeHandler(
        records_by_query={primary.cql_query: True},
    )

    result = PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert result.query is primary
    assert result.collection.verified_records
    assert result.attempted_queries == (primary,)
    assert handler.calls == [primary.cql_query]


def test_executor_uses_alternate_only_after_successful_zero_result_primary() -> None:
    plan = query_plan()
    primary, alternate = plan.queries
    handler = FakeHandler(
        records_by_query={
            primary.cql_query: False,
            alternate.cql_query: True,
        },
    )

    result = PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert result.query is alternate
    assert result.collection.verified_records
    assert result.attempted_queries == (primary, alternate)
    assert handler.calls == [
        primary.cql_query,
        alternate.cql_query,
    ]


def test_executor_returns_zero_result_primary_when_no_alternate_exists() -> None:
    plan = query_plan(include_alternate=False)
    primary = plan.queries[0]
    handler = FakeHandler()

    result = PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert result.query is primary
    assert result.collection.verified_records == ()
    assert result.attempted_queries == (primary,)
    assert handler.calls == [primary.cql_query]


def test_executor_returns_zero_result_alternate_after_two_empty_queries() -> None:
    plan = query_plan()
    primary, alternate = plan.queries
    handler = FakeHandler()

    result = PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert result.query is alternate
    assert result.collection.verified_records == ()
    assert result.attempted_queries == (primary, alternate)


def test_executor_does_not_fallback_on_primary_failure() -> None:
    plan = query_plan()
    primary, alternate = plan.queries
    error = RuntimeError("synthetic provider failure")
    handler = FakeHandler(
        error_by_query={primary.cql_query: error},
    )

    with pytest.raises(RuntimeError, match="synthetic provider failure"):
        PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert handler.calls == [primary.cql_query]
    assert alternate.cql_query not in handler.calls


def test_executor_rejects_handler_result_bound_to_other_request() -> None:
    plan = query_plan(include_alternate=False)
    handler = FakeHandler(mismatched_request=True)

    with pytest.raises(
        RuntimeError,
        match="not bound to the query-plan request",
    ):
        PatentResearchPlanExecutor(handler=handler).execute(plan)

    assert handler.calls == [plan.queries[0].cql_query]


def test_executor_is_deterministic_for_same_successful_plan() -> None:
    plan = query_plan()
    primary = plan.queries[0]

    first = PatentResearchPlanExecutor(
        handler=FakeHandler(records_by_query={primary.cql_query: True})
    ).execute(plan)
    second = PatentResearchPlanExecutor(
        handler=FakeHandler(records_by_query={primary.cql_query: True})
    ).execute(plan)

    assert first == second
