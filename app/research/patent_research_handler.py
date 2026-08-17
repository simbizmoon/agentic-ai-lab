"""Thin orchestration for bounded structured patent-source collection."""

from __future__ import annotations

from typing import Protocol

from app.research.epo_ops_patent_source_adapter import (
    build_verified_epo_patent_record,
)
from app.schemas.epo_ops_abstract import (
    EpoOpsAbstractRecord,
    EpoOpsVerifiedPatentRecord,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsSearchRequest,
)
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest


class PatentBibliographicSearcherProtocol(Protocol):
    """Search one explicitly supplied structured patent query."""

    def search(
        self,
        request: EpoOpsSearchRequest,
    ) -> EpoOpsBibliographicSearchResult:
        """Return bounded bibliographic candidates."""


class PatentAbstractRetrieverProtocol(Protocol):
    """Retrieve technical abstract text for one bibliographic candidate."""

    def retrieve(
        self,
        record: EpoOpsBibliographicRecord,
    ) -> EpoOpsAbstractRecord:
        """Return a source-specific abstract bound to the candidate."""


class VerifiedPatentRecordBuilderProtocol(Protocol):
    """Map matching provider records into one verified patent source."""

    def __call__(
        self,
        *,
        bibliographic: EpoOpsBibliographicRecord,
        abstract: EpoOpsAbstractRecord,
    ) -> EpoOpsVerifiedPatentRecord:
        """Return one verified patent record."""


class PatentResearchHandler:
    """Collect bounded verified EPO patent records without legal synthesis."""

    def __init__(
        self,
        *,
        searcher: PatentBibliographicSearcherProtocol,
        abstract_retriever: PatentAbstractRetrieverProtocol,
        record_builder: VerifiedPatentRecordBuilderProtocol = (
            build_verified_epo_patent_record
        ),
    ) -> None:
        self._searcher = searcher
        self._abstract_retriever = abstract_retriever
        self._record_builder = record_builder

    def run(
        self,
        request: PatentResearchRequest,
        *,
        cql_query: str,
    ) -> PatentResearchCollectionResult:
        """Search, retrieve, and verify up to the request source boundary.

        CQL generation is intentionally outside this Step 3A handler. The caller
        supplies an explicit CQL query, while the patent request remains the
        source of truth for search/result bounds.

        Candidate processing is fail-fast. Current OPS abstract exceptions do
        not yet distinguish safely skippable absence from provider-contract,
        identity, MIME, XML-safety, transport, or authentication failures.
        """

        search_request = EpoOpsSearchRequest(
            cql_query=cql_query,
            maximum_results=request.maximum_search_results,
        )
        search_result = self._searcher.search(search_request)
        if search_result.request != search_request:
            raise RuntimeError(
                "patent search result was not bound to the exact requested CQL"
            )
        if len(search_result.records) > request.maximum_search_results:
            raise RuntimeError("patent search result exceeded maximum_search_results")

        selected = search_result.records[: request.maximum_sources]
        verified_records: list[EpoOpsVerifiedPatentRecord] = []
        for bibliographic in selected:
            abstract = self._abstract_retriever.retrieve(bibliographic)
            verified_records.append(
                self._record_builder(
                    bibliographic=bibliographic,
                    abstract=abstract,
                )
            )

        return PatentResearchCollectionResult(
            request=request,
            search_result=search_result,
            verified_records=tuple(verified_records),
        )
