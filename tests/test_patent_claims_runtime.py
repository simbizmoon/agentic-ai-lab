"""Tests for companion patent-claims runtime wiring."""

from __future__ import annotations

from datetime import date

import pytest

from app.research.epo_ops_patent_source_adapter import (
    build_verified_epo_patent_record,
)
from app.research.patent_claims_runtime import PatentClaimsRuntime
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPurpose,
)


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="Which publications are technically relevant?",
        objective="Collect bounded verified patent sources.",
        maximum_search_results=2,
        maximum_sources=2,
        maximum_bytes=4096,
    )


def bibliographic(number: str, docdb: str) -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number=number,
        publication_docdb=docdb,
        title=f"Patent {number}",
        publication_date=date(2025, 1, 1),
        source_endpoint="https://ops.epo.org/search",
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )


def execution(
    records: tuple[EpoOpsBibliographicRecord, ...],
) -> PatentResearchPlanExecutionResult:
    source_request = request()
    query = PatentSearchQuery(
        cql_query='ta all "seat occupancy"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    search_request = EpoOpsSearchRequest(
        cql_query=query.cql_query,
        maximum_results=source_request.maximum_search_results,
    )

    verified = tuple(
        build_verified_epo_patent_record(
            bibliographic=record,
            abstract=EpoOpsAbstractRecord(
                publication_number=record.publication_number,
                publication_docdb=record.publication_docdb,
                abstract_text=f"Abstract for {record.publication_number}.",
                abstract_language="en",
                source_endpoint=(
                    "https://ops.epo.org/3.2/rest-services/published-data/"
                    f"publication/docdb/{record.publication_docdb}/abstract"
                ),
            ),
        )
        for record in records
    )

    return PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=source_request,
            search_result=EpoOpsBibliographicSearchResult(
                request=search_request,
                records=records,
            ),
            verified_records=verified,
        ),
        attempted_queries=(query,),
    )


class FakeClaimsRetriever:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[str] = []

    def retrieve(
        self,
        record: EpoOpsBibliographicRecord,
    ) -> EpoOpsClaimsRecord:
        self.calls.append(record.publication_number)
        if record.publication_number == self.fail_on:
            raise RuntimeError("synthetic claims retrieval failure")
        return EpoOpsClaimsRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/published-data/"
                f"publication/docdb/{record.publication_docdb}/claims"
            ),
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(
                        EpoOpsClaimText(
                            position=1,
                            text="1. First patent claim.",
                        ),
                        EpoOpsClaimText(
                            position=2,
                            text="2. Second patent claim.",
                        ),
                    ),
                ),
            ),
        )


def test_runtime_enriches_only_verified_publications_and_preserves_order() -> None:
    first = bibliographic("EP123456A1", "EP.123456.A1")
    second = bibliographic("EP654321B1", "EP.654321.B1")
    retriever = FakeClaimsRetriever()

    result = PatentClaimsRuntime(claims_retriever=retriever).enrich(
        execution((first, second))
    )

    assert retriever.calls == ["EP123456A1", "EP654321B1"]
    assert result.execution.collection.verified_records
    assert [document.publication_number for document in result.claim_documents] == [
        "EP123456A1",
        "EP654321B1",
    ]
    assert [
        document.claim_sets[0].claims[0].claim_number
        for document in result.claim_documents
    ] == [1, 1]


def test_runtime_returns_empty_claims_without_retrieval_for_zero_verified_records() -> (
    None
):
    source_request = request()
    query = PatentSearchQuery(
        cql_query='ta all "nothing"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    empty_execution = PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=source_request,
            search_result=EpoOpsBibliographicSearchResult(
                request=EpoOpsSearchRequest(
                    cql_query=query.cql_query,
                    maximum_results=source_request.maximum_search_results,
                ),
                records=(),
            ),
            verified_records=(),
        ),
        attempted_queries=(query,),
    )
    retriever = FakeClaimsRetriever()

    result = PatentClaimsRuntime(claims_retriever=retriever).enrich(empty_execution)

    assert result.claim_documents == ()
    assert retriever.calls == []


def test_runtime_is_fail_fast_on_claims_retrieval_failure() -> None:
    first = bibliographic("EP123456A1", "EP.123456.A1")
    second = bibliographic("EP654321B1", "EP.654321.B1")
    retriever = FakeClaimsRetriever(fail_on="EP654321B1")

    with pytest.raises(RuntimeError, match="synthetic claims retrieval failure"):
        PatentClaimsRuntime(claims_retriever=retriever).enrich(
            execution((first, second))
        )

    assert retriever.calls == ["EP123456A1", "EP654321B1"]


def test_runtime_rejects_parsed_claim_identity_drift() -> None:
    record = bibliographic("EP123456A1", "EP.123456.A1")
    retriever = FakeClaimsRetriever()

    def wrong_parser(raw: EpoOpsClaimsRecord):
        from app.research.patent_claim_parser import parse_epo_ops_claims_record

        parsed = parse_epo_ops_claims_record(raw)
        return parsed.model_copy(update={"publication_number": "EP999999A1"})

    with pytest.raises(RuntimeError, match="parsed patent claims identity drifted"):
        PatentClaimsRuntime(
            claims_retriever=retriever,
            claims_parser=wrong_parser,
        ).enrich(execution((record,)))


def test_runtime_rejects_parsed_claim_docdb_identity_drift() -> None:
    record = bibliographic("EP123456A1", "EP.123456.A1")
    retriever = FakeClaimsRetriever()

    def wrong_parser(raw: EpoOpsClaimsRecord):
        from app.research.patent_claim_parser import parse_epo_ops_claims_record

        parsed = parse_epo_ops_claims_record(raw)
        return parsed.model_copy(update={"publication_docdb": "EP.999999.A1"})

    with pytest.raises(RuntimeError, match="DOCDB identity drifted"):
        PatentClaimsRuntime(
            claims_retriever=retriever,
            claims_parser=wrong_parser,
        ).enrich(execution((record,)))
