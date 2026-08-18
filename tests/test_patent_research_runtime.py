"""Tests for end-to-end bounded patent research runtime composition."""

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
from app.research.patent_research_runtime import (
    PatentResearchRuntime,
    build_openai_epo_patent_research_runtime,
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
from app.services.text_generation import TokenUsage


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How can pressure sensors detect seat occupancy?",
        objective="Identify pressure sensors for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=1,
        maximum_bytes=4096,
    )


def concept_result(source_request: PatentResearchRequest):
    return PatentTechnicalConceptGenerationResult(
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


class FakeConceptGenerator:
    def __init__(
        self,
        *,
        result_request: PatentResearchRequest | None = None,
    ) -> None:
        self.result_request = result_request
        self.calls: list[PatentResearchRequest] = []

    def generate(
        self,
        source_request: PatentResearchRequest,
    ) -> PatentTechnicalConceptGenerationResult:
        self.calls.append(source_request)
        return concept_result(self.result_request or source_request)


class FakeCqlPlanner:
    def __init__(
        self,
        *,
        result_request: PatentResearchRequest | None = None,
    ) -> None:
        self.result_request = result_request
        self.calls = []

    def plan(self, concept_plan: PatentTechnicalConceptPlan) -> PatentSearchQueryPlan:
        self.calls.append(concept_plan)
        return PatentSearchQueryPlan(
            request=self.result_request or concept_plan.request,
            queries=(
                PatentSearchQuery(
                    cql_query=('ta all "pressure sensors" and ta all "seat occupancy"'),
                    purpose=PatentSearchQueryPurpose.PRIMARY,
                ),
            ),
        )


class FakeExecutionRuntime:
    def __init__(
        self,
        *,
        result_request: PatentResearchRequest | None = None,
    ) -> None:
        self.result_request = result_request
        self.calls: list[PatentSearchQueryPlan] = []

    def execute(
        self,
        plan: PatentSearchQueryPlan,
    ) -> PatentResearchPlanExecutionResult:
        self.calls.append(plan)
        source_request = self.result_request or plan.request
        query = plan.queries[0]
        search_request = EpoOpsSearchRequest(
            cql_query=query.cql_query,
            maximum_results=source_request.maximum_search_results,
        )
        collection = PatentResearchCollectionResult(
            request=source_request,
            search_result=EpoOpsBibliographicSearchResult(
                request=search_request,
                records=(),
            ),
            verified_records=(),
        )
        return PatentResearchPlanExecutionResult(
            query=query,
            collection=collection,
            attempted_queries=(query,),
        )


def test_runtime_connects_generation_planning_and_execution() -> None:
    source_request = request()
    generator = FakeConceptGenerator()
    planner = FakeCqlPlanner()
    executor = FakeExecutionRuntime()

    result = PatentResearchRuntime(
        concept_generator=generator,
        cql_planner=planner,
        execution_runtime=executor,
    ).execute(source_request)

    assert generator.calls == [source_request]
    assert planner.calls == [result.concept_generation.plan]
    assert executor.calls == [result.query_plan]
    assert result.concept_generation.response_id == "resp-test"
    assert result.concept_generation.usage is not None
    assert result.concept_generation.usage.total_tokens == 15
    assert result.query_plan.request == source_request
    assert result.execution.collection.request == source_request


def test_runtime_preserves_request_maximum_bytes_through_query_plan() -> None:
    result = PatentResearchRuntime(
        concept_generator=FakeConceptGenerator(),
        cql_planner=FakeCqlPlanner(),
        execution_runtime=FakeExecutionRuntime(),
    ).execute(request())

    assert result.query_plan.request.maximum_bytes == 4096
    assert result.execution.collection.request.maximum_bytes == 4096


def test_runtime_rejects_mismatched_concept_request() -> None:
    source_request = request()
    mismatched = source_request.model_copy(
        update={"objective": "Different objective for mismatch."},
    )
    runtime = PatentResearchRuntime(
        concept_generator=FakeConceptGenerator(result_request=mismatched),
        cql_planner=FakeCqlPlanner(),
        execution_runtime=FakeExecutionRuntime(),
    )

    with pytest.raises(RuntimeError, match="concept generation"):
        runtime.execute(source_request)


def test_runtime_rejects_mismatched_query_plan_request() -> None:
    source_request = request()
    mismatched = source_request.model_copy(
        update={"objective": "Different objective for mismatch."},
    )
    runtime = PatentResearchRuntime(
        concept_generator=FakeConceptGenerator(),
        cql_planner=FakeCqlPlanner(result_request=mismatched),
        execution_runtime=FakeExecutionRuntime(),
    )

    with pytest.raises(RuntimeError, match="query plan"):
        runtime.execute(source_request)


def test_runtime_rejects_mismatched_execution_request() -> None:
    source_request = request()
    mismatched = source_request.model_copy(
        update={"objective": "Different objective for mismatch."},
    )
    runtime = PatentResearchRuntime(
        concept_generator=FakeConceptGenerator(),
        cql_planner=FakeCqlPlanner(),
        execution_runtime=FakeExecutionRuntime(result_request=mismatched),
    )

    with pytest.raises(RuntimeError, match="execution result"):
        runtime.execute(source_request)


def test_production_builder_uses_supplied_settings_and_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        openai_api_key="secret",
        openai_model="test-model",
        openai_timeout_seconds=30.0,
        openai_max_retries=2,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )
    fake_client = SimpleNamespace(responses=SimpleNamespace())
    executor = FakeExecutionRuntime()
    calls: list[str] = []

    monkeypatch.setattr(
        "app.research.patent_research_runtime.load_settings",
        lambda: (_ for _ in ()).throw(AssertionError("must not load settings")),
    )
    monkeypatch.setattr(
        "app.research.patent_research_runtime.create_openai_client",
        lambda _settings: (
            calls.append("client"),
            fake_client,
        )[1],
    )

    runtime = build_openai_epo_patent_research_runtime(
        settings=settings,
        openai_client=fake_client,  # type: ignore[arg-type]
        execution_runtime=executor,
    )

    assert isinstance(runtime, PatentResearchRuntime)
    assert calls == []


def test_production_builder_creates_openai_client_when_not_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        openai_api_key="secret",
        openai_model="test-model",
        openai_timeout_seconds=30.0,
        openai_max_retries=2,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )
    fake_client = SimpleNamespace(responses=SimpleNamespace())
    seen = []

    monkeypatch.setattr(
        "app.research.patent_research_runtime.create_openai_client",
        lambda actual_settings: (
            seen.append(actual_settings),
            fake_client,
        )[1],
    )

    runtime = build_openai_epo_patent_research_runtime(
        settings=settings,
        execution_runtime=FakeExecutionRuntime(),
    )

    assert isinstance(runtime, PatentResearchRuntime)
    assert seen == [settings]
