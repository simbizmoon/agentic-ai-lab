"""Tests for thin bounded patent-source orchestration."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.research.epo_ops_abstract_retriever import EpoOpsAbstractResponseError
from app.research.patent_research_handler import PatentResearchHandler
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_source_metadata import PatentMetadataVerificationState


def patent_request(**overrides: object) -> PatentResearchRequest:
    values: dict[str, object] = {
        "question": "Which publications are technically relevant?",
        "objective": "Collect bounded verified patent sources.",
        "maximum_search_results": 4,
        "maximum_sources": 2,
    }
    values.update(overrides)
    return PatentResearchRequest.model_validate(values)


def bibliographic(index: int) -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number=f"EPTEST000{index}A1",
        publication_docdb=f"EP.TEST000{index}.A1",
        title=f"Test patent {index}",
        publication_date=date(2024, 1, index),
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/search/biblio?q=ab%3Dtest"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )


class FakeSearcher:
    def __init__(
        self,
        records: tuple[EpoOpsBibliographicRecord, ...],
    ) -> None:
        self.records = records
        self.calls: list[EpoOpsSearchRequest] = []

    def search(
        self,
        request: EpoOpsSearchRequest,
    ) -> EpoOpsBibliographicSearchResult:
        self.calls.append(request)
        return EpoOpsBibliographicSearchResult(
            request=request,
            records=self.records,
        )


class FakeAbstractRetriever:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[str] = []

    def retrieve(
        self,
        record: EpoOpsBibliographicRecord,
    ) -> EpoOpsAbstractRecord:
        self.calls.append(record.publication_number)
        if record.publication_number == self.fail_on:
            raise EpoOpsAbstractResponseError("synthetic candidate retrieval failure")
        return EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text=f"Technical abstract for {record.publication_number}.",
            abstract_language="en",
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/docdb/"
                f"{record.publication_docdb}/abstract"
            ),
        )


def test_handler_wires_explicit_cql_and_request_search_bound() -> None:
    records = (bibliographic(1),)
    searcher = FakeSearcher(records)
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    result = handler.run(
        patent_request(maximum_search_results=3, maximum_sources=1),
        cql_query='ab="seat detection"',
    )

    assert len(searcher.calls) == 1
    assert searcher.calls[0].cql_query == 'ab="seat detection"'
    assert searcher.calls[0].maximum_results == 3
    assert result.search_result.request == searcher.calls[0]


def test_handler_retrieves_only_maximum_sources_and_builds_verified_records() -> None:
    records = tuple(bibliographic(index) for index in range(1, 5))
    searcher = FakeSearcher(records)
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    result = handler.run(
        patent_request(maximum_search_results=4, maximum_sources=2),
        cql_query="ab=test",
    )

    assert retriever.calls == [
        "EPTEST0001A1",
        "EPTEST0002A1",
    ]
    assert [
        record.metadata.publication_number for record in result.verified_records
    ] == [
        "EPTEST0001A1",
        "EPTEST0002A1",
    ]
    assert all(
        record.metadata.metadata_verification_state
        is PatentMetadataVerificationState.VERIFIED
        for record in result.verified_records
    )


def test_handler_allows_zero_search_results_without_retrieval() -> None:
    searcher = FakeSearcher(())
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    result = handler.run(
        patent_request(),
        cql_query="ab=unfindable",
    )

    assert result.verified_records == ()
    assert retriever.calls == []


def test_handler_is_fail_fast_on_selected_candidate_retrieval_failure() -> None:
    records = tuple(bibliographic(index) for index in range(1, 4))
    searcher = FakeSearcher(records)
    retriever = FakeAbstractRetriever(fail_on="EPTEST0002A1")
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    with pytest.raises(
        EpoOpsAbstractResponseError,
        match="synthetic candidate retrieval failure",
    ):
        handler.run(
            patent_request(maximum_search_results=3, maximum_sources=3),
            cql_query="ab=test",
        )

    assert retriever.calls == [
        "EPTEST0001A1",
        "EPTEST0002A1",
    ]


def test_handler_rejects_blank_cql_before_searcher_call() -> None:
    searcher = FakeSearcher(())
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    with pytest.raises(ValidationError):
        handler.run(
            patent_request(),
            cql_query=" ",
        )

    assert searcher.calls == []
    assert retriever.calls == []


def test_collection_result_rejects_missing_or_reordered_selected_records() -> None:
    from app.research.epo_ops_patent_source_adapter import (
        build_verified_epo_patent_record,
    )
    from app.schemas.patent_research_collection_result import (
        PatentResearchCollectionResult,
    )

    request = patent_request(maximum_search_results=3, maximum_sources=2)
    records = tuple(bibliographic(index) for index in range(1, 4))
    search_request = EpoOpsSearchRequest(
        cql_query="ab=test",
        maximum_results=3,
    )
    search_result = EpoOpsBibliographicSearchResult(
        request=search_request,
        records=records,
    )
    retriever = FakeAbstractRetriever()
    first = build_verified_epo_patent_record(
        bibliographic=records[0],
        abstract=retriever.retrieve(records[0]),
    )
    second = build_verified_epo_patent_record(
        bibliographic=records[1],
        abstract=retriever.retrieve(records[1]),
    )

    with pytest.raises(
        ValidationError,
        match="verify every selected candidate",
    ):
        PatentResearchCollectionResult(
            request=request,
            search_result=search_result,
            verified_records=(first,),
        )

    with pytest.raises(
        ValidationError,
        match="preserve the selected candidate identities and order",
    ):
        PatentResearchCollectionResult(
            request=request,
            search_result=search_result,
            verified_records=(second, first),
        )


class MismatchedRequestSearcher(FakeSearcher):
    def search(
        self,
        request: EpoOpsSearchRequest,
    ) -> EpoOpsBibliographicSearchResult:
        self.calls.append(request)
        return EpoOpsBibliographicSearchResult(
            request=EpoOpsSearchRequest(
                cql_query="ab=other",
                maximum_results=request.maximum_results,
            ),
            records=self.records,
        )


def test_handler_rejects_search_result_not_bound_to_exact_cql_request() -> None:
    searcher = MismatchedRequestSearcher((bibliographic(1),))
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    with pytest.raises(RuntimeError, match="exact requested CQL"):
        handler.run(
            patent_request(maximum_search_results=2, maximum_sources=1),
            cql_query="ab=test",
        )

    assert retriever.calls == []


def test_handler_rejects_provider_result_exceeding_search_bound() -> None:
    records = tuple(bibliographic(index) for index in range(1, 4))
    searcher = FakeSearcher(records)
    retriever = FakeAbstractRetriever()
    handler = PatentResearchHandler(
        searcher=searcher,
        abstract_retriever=retriever,
    )

    with pytest.raises(RuntimeError, match="exceeded maximum_search_results"):
        handler.run(
            patent_request(maximum_search_results=2, maximum_sources=1),
            cql_query="ab=test",
        )

    assert retriever.calls == []
