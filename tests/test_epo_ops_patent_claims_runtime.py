"""Tests for EPO OPS companion claims runtime composition."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr

from app.research.epo_ops_patent_claims_runtime import EpoOpsPatentClaimsRuntime
from app.research.epo_ops_patent_source_adapter import (
    build_verified_epo_patent_record,
)
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
from app.schemas.epo_ops_config import EpoOpsConfig
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPurpose,
)


class FakeClient:
    pass


class FakeClaimsRetriever:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        self.calls.append(record.publication_number)
        return EpoOpsClaimsRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            source_endpoint=f"https://ops.epo.org/{record.publication_docdb}/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(EpoOpsClaimText(position=1, text="1. Claim text."),),
                ),
            ),
        )


def execution() -> PatentResearchPlanExecutionResult:
    source_request = PatentResearchRequest(
        question="Which patents are relevant?",
        objective="Collect patent sources.",
        maximum_search_results=1,
        maximum_sources=1,
        maximum_bytes=4096,
    )
    record = EpoOpsBibliographicRecord(
        publication_number="EP123456A1",
        publication_docdb="EP.123456.A1",
        title="Test patent",
        publication_date=date(2025, 1, 1),
        source_endpoint="https://ops.epo.org/search",
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )
    abstract = EpoOpsAbstractRecord(
        publication_number=record.publication_number,
        publication_docdb=record.publication_docdb,
        abstract_text="Technical abstract.",
        abstract_language="en",
        source_endpoint="https://ops.epo.org/EP.123456.A1/abstract",
    )
    query = PatentSearchQuery(
        cql_query='ta all "test"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    return PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=source_request,
            search_result=EpoOpsBibliographicSearchResult(
                request=EpoOpsSearchRequest(
                    cql_query=query.cql_query,
                    maximum_results=1,
                ),
                records=(record,),
            ),
            verified_records=(
                build_verified_epo_patent_record(
                    bibliographic=record,
                    abstract=abstract,
                ),
            ),
        ),
        attempted_queries=(query,),
    )


def test_epo_runtime_binds_request_maximum_bytes_and_composes_claims() -> None:
    seen: dict[str, object] = {}
    retriever = FakeClaimsRetriever()

    def config_loader(maximum_bytes: int) -> EpoOpsConfig:
        seen["maximum_bytes"] = maximum_bytes
        return EpoOpsConfig(
            consumer_key=SecretStr("key"),
            consumer_secret=SecretStr("secret"),
            maximum_response_bytes=maximum_bytes,
        )

    result = EpoOpsPatentClaimsRuntime(
        config_loader=config_loader,
        client_factory=lambda _config: FakeClient(),  # type: ignore[arg-type]
        claims_retriever_factory=lambda _client: retriever,  # type: ignore[arg-type]
    ).enrich(execution())

    assert seen["maximum_bytes"] == 4096
    assert retriever.calls == ["EP123456A1"]
    assert result.claim_documents[0].publication_docdb == "EP.123456.A1"


def test_epo_claims_runtime_preserves_existing_execution_without_mutating_collection() -> (
    None
):
    source_execution = execution()
    original_verified = source_execution.collection.verified_records
    original_search_records = source_execution.collection.search_result.records
    retriever = FakeClaimsRetriever()

    result = EpoOpsPatentClaimsRuntime(
        config_loader=lambda maximum_bytes: EpoOpsConfig(
            consumer_key=SecretStr("key"),
            consumer_secret=SecretStr("secret"),
            maximum_response_bytes=maximum_bytes,
        ),
        client_factory=lambda _config: FakeClient(),  # type: ignore[arg-type]
        claims_retriever_factory=lambda _client: retriever,  # type: ignore[arg-type]
    ).enrich(source_execution)

    assert result.execution is source_execution
    assert result.execution.collection.verified_records == original_verified
    assert result.execution.collection.search_result.records == original_search_records
    assert len(result.claim_documents) == 1
    assert result.claim_documents[0].publication_number == "EP123456A1"


def test_epo_claims_runtime_does_not_change_existing_query_or_attempt_history() -> None:
    source_execution = execution()
    original_query = source_execution.query
    original_attempted = source_execution.attempted_queries
    retriever = FakeClaimsRetriever()

    result = EpoOpsPatentClaimsRuntime(
        config_loader=lambda maximum_bytes: EpoOpsConfig(
            consumer_key=SecretStr("key"),
            consumer_secret=SecretStr("secret"),
            maximum_response_bytes=maximum_bytes,
        ),
        client_factory=lambda _config: FakeClient(),  # type: ignore[arg-type]
        claims_retriever_factory=lambda _client: retriever,  # type: ignore[arg-type]
    ).enrich(source_execution)

    assert result.execution.query == original_query
    assert result.execution.attempted_queries == original_attempted
    assert retriever.calls == ["EP123456A1"]
