"""Tests for request-bound EPO OPS patent runtime composition."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import SecretStr

from app.research.epo_ops_patent_runtime import (
    EPO_OPS_CONSUMER_KEY_ENV,
    EPO_OPS_CONSUMER_SECRET_ENV,
    EpoOpsPatentRuntime,
    load_epo_ops_config,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
)
from app.schemas.epo_ops_config import EpoOpsConfig
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPlan,
    PatentSearchQueryPurpose,
)


def request(*, maximum_bytes: int = 2048) -> PatentResearchRequest:
    return PatentResearchRequest(
        question="Which seat occupancy patents are technically relevant?",
        objective="Collect bounded verified patent sources for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=1,
        maximum_bytes=maximum_bytes,
    )


def plan(*, maximum_bytes: int = 2048) -> PatentSearchQueryPlan:
    return PatentSearchQueryPlan(
        request=request(maximum_bytes=maximum_bytes),
        queries=(
            PatentSearchQuery(
                cql_query='ta all "seat occupancy"',
                purpose=PatentSearchQueryPurpose.PRIMARY,
            ),
        ),
    )


class FakeClient:
    pass


class FakeSearcher:
    def __init__(self, *, records: tuple[EpoOpsBibliographicRecord, ...] = ()) -> None:
        self.records = records
        self.calls = []

    def search(self, search_request):
        self.calls.append(search_request)
        return EpoOpsBibliographicSearchResult(
            request=search_request,
            records=self.records,
        )


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        self.calls.append(record.publication_number)
        return EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text="A pressure sensor detects seat occupancy.",
            abstract_language="en",
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/docdb/{record.publication_docdb}/abstract"
            ),
        )


def bibliographic() -> EpoOpsBibliographicRecord:
    return EpoOpsBibliographicRecord(
        publication_number="EP123456A1",
        publication_docdb="EP.123456.A1",
        title="Seat occupancy detector",
        publication_date=date(2024, 1, 1),
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=test"
        ),
        document_id_type=EpoOpsDocumentIdType.DOCDB,
        application_number=None,
        title_language="en",
    )


def test_runtime_binds_request_maximum_bytes_to_epo_config() -> None:
    seen: dict[str, object] = {}
    searcher = FakeSearcher()

    def config_loader(maximum_response_bytes: int) -> EpoOpsConfig:
        seen["maximum_response_bytes"] = maximum_response_bytes
        return EpoOpsConfig(
            consumer_key=SecretStr("consumer-key"),
            consumer_secret=SecretStr("consumer-secret"),
            maximum_response_bytes=maximum_response_bytes,
        )

    def client_factory(config: EpoOpsConfig) -> FakeClient:
        seen["config"] = config
        return FakeClient()

    result = EpoOpsPatentRuntime(
        config_loader=config_loader,
        client_factory=client_factory,  # type: ignore[arg-type]
        searcher_factory=lambda _client: searcher,  # type: ignore[arg-type]
        abstract_retriever_factory=lambda _client: FakeRetriever(),  # type: ignore[arg-type]
    ).execute(plan(maximum_bytes=4096))

    assert seen["maximum_response_bytes"] == 4096
    config = seen["config"]
    assert isinstance(config, EpoOpsConfig)
    assert config.maximum_response_bytes == 4096
    assert result.collection.request.maximum_bytes == 4096
    assert len(searcher.calls) == 1


def test_runtime_rejects_config_loader_that_breaks_request_byte_binding() -> None:
    runtime = EpoOpsPatentRuntime(
        config_loader=lambda _maximum_bytes: EpoOpsConfig(
            consumer_key=SecretStr("consumer-key"),
            consumer_secret=SecretStr("consumer-secret"),
            maximum_response_bytes=8192,
        ),
    )

    with pytest.raises(RuntimeError, match="not bound"):
        runtime.execute(plan(maximum_bytes=4096))


def test_runtime_composes_search_and_abstract_retrieval() -> None:
    searcher = FakeSearcher(records=(bibliographic(),))
    retriever = FakeRetriever()

    result = EpoOpsPatentRuntime(
        config_loader=lambda maximum_bytes: EpoOpsConfig(
            consumer_key=SecretStr("consumer-key"),
            consumer_secret=SecretStr("consumer-secret"),
            maximum_response_bytes=maximum_bytes,
        ),
        client_factory=lambda _config: FakeClient(),  # type: ignore[arg-type]
        searcher_factory=lambda _client: searcher,  # type: ignore[arg-type]
        abstract_retriever_factory=lambda _client: retriever,  # type: ignore[arg-type]
    ).execute(plan())

    assert len(result.collection.verified_records) == 1
    assert result.collection.verified_records[0].metadata.publication_number == (
        "EP123456A1"
    )
    assert retriever.calls == ["EP123456A1"]


def test_load_epo_ops_config_reads_credentials_without_exposing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(EPO_OPS_CONSUMER_KEY_ENV, "consumer-key")
    monkeypatch.setenv(EPO_OPS_CONSUMER_SECRET_ENV, "consumer-secret")

    config = load_epo_ops_config(4096)

    assert config.maximum_response_bytes == 4096
    assert config.consumer_key.get_secret_value() == "consumer-key"
    assert config.consumer_secret.get_secret_value() == "consumer-secret"
    assert "consumer-key" not in repr(config)
    assert "consumer-secret" not in repr(config)


@pytest.mark.parametrize(
    "missing_name",
    [
        EPO_OPS_CONSUMER_KEY_ENV,
        EPO_OPS_CONSUMER_SECRET_ENV,
    ],
)
def test_load_epo_ops_config_rejects_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    monkeypatch.setenv(EPO_OPS_CONSUMER_KEY_ENV, "consumer-key")
    monkeypatch.setenv(EPO_OPS_CONSUMER_SECRET_ENV, "consumer-secret")
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(RuntimeError, match=f"{missing_name} is required"):
        load_epo_ops_config(4096)
