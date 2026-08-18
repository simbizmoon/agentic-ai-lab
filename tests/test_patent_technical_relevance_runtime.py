"""Tests for end-to-end patent technical-relevance composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.research.openai_patent_technical_concept_generator import (
    PatentTechnicalConceptGenerationResult,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.research.patent_research_runtime import PatentResearchRuntimeResult
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.research.patent_technical_relevance_runtime import (
    PatentTechnicalRelevanceRuntime,
    build_openai_epo_patent_technical_relevance_runtime,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicSearchResult,
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
from app.schemas.patent_technical_concept import (
    PatentTechnicalConcept,
    PatentTechnicalConceptPlan,
    PatentTechnicalConceptRole,
)
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_source_document import ResearchSourceDocumentSet
from app.services.text_generation import TokenUsage


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How can pressure sensors detect seat occupancy?",
        objective="Identify pressure sensors for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=1,
        maximum_bytes=4096,
    )


def research_result(
    source_request: PatentResearchRequest,
) -> PatentResearchRuntimeResult:
    query = PatentSearchQuery(
        cql_query='ta all "pressure sensors" and ta all "seat occupancy"',
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    search_request = EpoOpsSearchRequest(
        cql_query=query.cql_query,
        maximum_results=source_request.maximum_search_results,
    )
    execution = PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=source_request,
            search_result=EpoOpsBibliographicSearchResult(
                request=search_request,
                records=(),
            ),
            verified_records=(),
        ),
        attempted_queries=(query,),
    )
    concept_generation = PatentTechnicalConceptGenerationResult(
        plan=PatentTechnicalConceptPlan(
            request=source_request,
            concepts=(
                PatentTechnicalConcept(
                    role=PatentTechnicalConceptRole.PRIMARY,
                    terms=("pressure sensors", "seat occupancy"),
                ),
            ),
        ),
        response_id="resp-test",
        request_id="req-test",
        usage=TokenUsage(
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            reasoning_tokens=0,
            total_tokens=15,
        ),
        elapsed_seconds=0.1,
    )
    return PatentResearchRuntimeResult(
        concept_generation=concept_generation,
        query_plan=PatentSearchQueryPlan(
            request=source_request,
            queries=(query,),
        ),
        execution=execution,
    )


class FakePatentRuntime:
    def __init__(
        self,
        *,
        result_request: PatentResearchRequest | None = None,
    ) -> None:
        self.result_request = result_request
        self.calls: list[PatentResearchRequest] = []

    def execute(
        self,
        source_request: PatentResearchRequest,
    ) -> PatentResearchRuntimeResult:
        self.calls.append(source_request)
        return research_result(self.result_request or source_request)


class FakeEvidenceRuntime:
    def __init__(
        self,
        *,
        preserve_execution: bool = True,
    ) -> None:
        self.preserve_execution = preserve_execution
        self.calls = []

    def extract(
        self,
        execution,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalRelevanceEvidenceResult:
        self.calls.append((execution, request_id, task_id))
        document_set = ResearchSourceDocumentSet(
            request_id=request_id,
            documents=[],
        )
        evidence_set = ResearchEvidenceSet(
            request_id=request_id,
            document_set=document_set,
            evidence=[],
        )
        returned_execution = execution
        if not self.preserve_execution:
            changed_request = execution.collection.request.model_copy(
                update={"objective": "Different objective."},
            )
            returned_execution = research_result(changed_request).execution
        return PatentTechnicalRelevanceEvidenceResult(
            execution=returned_execution,
            document_set=document_set,
            evidence_set=evidence_set,
        )


def test_runtime_connects_patent_collection_to_relevance_evidence() -> None:
    source_request = request()
    patent_runtime = FakePatentRuntime()
    evidence_runtime = FakeEvidenceRuntime()
    factory_calls = []

    runtime = PatentTechnicalRelevanceRuntime(
        patent_runtime=patent_runtime,
        evidence_runtime_factory=lambda actual_request: (
            factory_calls.append(actual_request),
            evidence_runtime,
        )[1],
    )

    result = runtime.execute(
        source_request,
        request_id="patent-analysis-001",
        task_id="technical-relevance",
    )

    assert patent_runtime.calls == [source_request]
    assert factory_calls == [source_request]
    assert evidence_runtime.calls == [
        (
            result.research.execution,
            "patent-analysis-001",
            "technical-relevance",
        )
    ]
    assert result.relevance.execution == result.research.execution
    assert result.relevance.evidence_set.request_id == "patent-analysis-001"


def test_runtime_rejects_mismatched_patent_request_binding() -> None:
    source_request = request()
    mismatched = source_request.model_copy(
        update={"objective": "Different objective."},
    )
    runtime = PatentTechnicalRelevanceRuntime(
        patent_runtime=FakePatentRuntime(result_request=mismatched),
        evidence_runtime_factory=lambda _request: FakeEvidenceRuntime(),
    )

    with pytest.raises(RuntimeError, match="exact request"):
        runtime.execute(
            source_request,
            request_id="patent-analysis-002",
        )


def test_runtime_rejects_relevance_execution_drift() -> None:
    runtime = PatentTechnicalRelevanceRuntime(
        patent_runtime=FakePatentRuntime(),
        evidence_runtime_factory=lambda _request: FakeEvidenceRuntime(
            preserve_execution=False,
        ),
    )

    with pytest.raises(RuntimeError, match="did not preserve"):
        runtime.execute(
            request(),
            request_id="patent-analysis-003",
        )


def settings() -> Settings:
    return Settings(
        openai_api_key="secret",
        openai_model="test-model",
        openai_timeout_seconds=30.0,
        openai_max_retries=2,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )


def test_production_builder_reuses_supplied_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = settings()
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(),
        embeddings=SimpleNamespace(),
    )
    patent_runtime = FakePatentRuntime()

    monkeypatch.setattr(
        "app.research.patent_technical_relevance_runtime.create_openai_client",
        lambda _settings: (_ for _ in ()).throw(
            AssertionError("must not create client")
        ),
    )
    monkeypatch.setattr(
        "app.research.patent_technical_relevance_runtime."
        "build_openai_epo_patent_research_runtime",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("must use supplied patent runtime")
        ),
    )

    runtime = build_openai_epo_patent_technical_relevance_runtime(
        settings=configured,
        openai_client=fake_client,  # type: ignore[arg-type]
        patent_runtime=patent_runtime,
    )

    assert isinstance(runtime, PatentTechnicalRelevanceRuntime)


def test_production_builder_creates_client_once_when_not_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = settings()
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(),
        embeddings=SimpleNamespace(),
    )
    client_calls = []
    patent_builder_calls = []

    monkeypatch.setattr(
        "app.research.patent_technical_relevance_runtime.create_openai_client",
        lambda actual_settings: (
            client_calls.append(actual_settings),
            fake_client,
        )[1],
    )
    monkeypatch.setattr(
        "app.research.patent_technical_relevance_runtime."
        "build_openai_epo_patent_research_runtime",
        lambda **kwargs: (
            patent_builder_calls.append(kwargs),
            FakePatentRuntime(),
        )[1],
    )

    runtime = build_openai_epo_patent_technical_relevance_runtime(
        settings=configured,
    )

    assert isinstance(runtime, PatentTechnicalRelevanceRuntime)
    assert client_calls == [configured]
    assert len(patent_builder_calls) == 1
    assert patent_builder_calls[0]["settings"] is configured
    assert patent_builder_calls[0]["openai_client"] is fake_client
