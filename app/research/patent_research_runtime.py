"""End-to-end bounded patent planning and EPO execution composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.config import Settings, load_settings
from app.research.epo_ops_patent_cql_planner import EpoOpsPatentCqlPlanner
from app.research.epo_ops_patent_runtime import EpoOpsPatentRuntime
from app.research.openai_patent_technical_concept_generator import (
    OpenAIPatentTechnicalConceptGenerator,
    PatentTechnicalConceptGenerationResult,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import PatentSearchQueryPlan
from app.services.openai_client import create_openai_client


class PatentConceptGeneratorProtocol(Protocol):
    """Minimal request-to-grounded-concept contract."""

    def generate(
        self,
        request: PatentResearchRequest,
    ) -> PatentTechnicalConceptGenerationResult:
        """Return one request-bound grounded technical concept plan."""


class PatentCqlPlannerProtocol(Protocol):
    """Minimal grounded-concept to provider-query contract."""

    def plan(
        self,
        concept_plan,
    ) -> PatentSearchQueryPlan:
        """Return one validated bounded patent query plan."""


class PatentExecutionRuntimeProtocol(Protocol):
    """Minimal validated-query-plan execution contract."""

    def execute(
        self,
        plan: PatentSearchQueryPlan,
    ) -> PatentResearchPlanExecutionResult:
        """Execute one bounded patent query plan."""


@dataclass(frozen=True)
class PatentResearchRuntimeResult:
    """One end-to-end patent planning and collection result."""

    concept_generation: PatentTechnicalConceptGenerationResult
    query_plan: PatentSearchQueryPlan
    execution: PatentResearchPlanExecutionResult


class PatentResearchRuntime:
    """Run grounded patent planning and bounded EPO collection."""

    def __init__(
        self,
        *,
        concept_generator: PatentConceptGeneratorProtocol,
        cql_planner: PatentCqlPlannerProtocol | None = None,
        execution_runtime: PatentExecutionRuntimeProtocol | None = None,
    ) -> None:
        self._concept_generator = concept_generator
        self._cql_planner = cql_planner or EpoOpsPatentCqlPlanner()
        self._execution_runtime = execution_runtime or EpoOpsPatentRuntime()

    def execute(
        self,
        request: PatentResearchRequest,
    ) -> PatentResearchRuntimeResult:
        """Generate grounded concepts, render CQL, and execute the plan."""

        concept_generation = self._concept_generator.generate(request)
        if concept_generation.plan.request != request:
            raise RuntimeError(
                "patent concept generation was not bound to the exact request"
            )

        query_plan = self._cql_planner.plan(concept_generation.plan)
        if query_plan.request != request:
            raise RuntimeError("patent query plan was not bound to the exact request")

        execution = self._execution_runtime.execute(query_plan)
        if execution.collection.request != request:
            raise RuntimeError(
                "patent execution result was not bound to the exact request"
            )

        return PatentResearchRuntimeResult(
            concept_generation=concept_generation,
            query_plan=query_plan,
            execution=execution,
        )


def build_openai_epo_patent_research_runtime(
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
    execution_runtime: PatentExecutionRuntimeProtocol | None = None,
) -> PatentResearchRuntime:
    """Build the production OpenAI-planning + EPO-execution patent runtime."""

    resolved_settings = settings or load_settings()
    resolved_client = openai_client or create_openai_client(resolved_settings)

    return PatentResearchRuntime(
        concept_generator=OpenAIPatentTechnicalConceptGenerator(
            client=resolved_client,
            model=resolved_settings.openai_model,
        ),
        execution_runtime=execution_runtime,
    )
