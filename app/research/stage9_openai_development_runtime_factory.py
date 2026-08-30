"""Compose the locked OpenAI and acquisition runtime for Stage 9 development."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from app.planning.openai_planner_client import OpenAIPlannerClient
from app.research.bounded_grounded_answer_factory import (
    create_bounded_grounded_answer_orchestrator,
)
from app.research.openai_semantic_citation_evaluator import (
    OpenAISemanticCitationEvaluator,
)
from app.research.stage9_development_runtime_factory import Stage9DevelopmentRuntime
from app.research.stage9_packed_research_loop_factory import (
    Stage9PackedResearchLoopFactory,
)
from app.research.stage9_planner_usage_accounting import Stage9MeteredPlannerClient
from app.research.stage9_real_development_runtime_factory import (
    create_stage9_real_development_runtime,
)
from app.schemas.planner_client_config import PlannerClientConfig
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9LockedBaselineExperiment,
    Stage9RuntimeComponentRole,
)


def create_stage9_openai_development_runtime(
    *,
    experiment: Stage9LockedBaselineExperiment,
    environ: Mapping[str, str],
    repository_root: Path,
    openai_client: Any,
    tavily_client: httpx.Client | None = None,
    openalex_client: httpx.Client | None = None,
    epo_client: httpx.Client | None = None,
) -> Stage9DevelopmentRuntime:
    """Compose every locked component without starting provider execution."""

    if not isinstance(experiment, Stage9LockedBaselineExperiment):
        raise TypeError("experiment must be a locked Stage 9 experiment")
    responses = getattr(openai_client, "responses", None)
    if responses is None or not callable(getattr(responses, "create", None)):
        raise TypeError("openai_client must expose responses.create")
    if not callable(getattr(responses, "parse", None)):
        raise TypeError("openai_client must expose responses.parse")

    planner_lock = experiment.runtime_stack.component(
        Stage9RuntimeComponentRole.PLANNER
    )
    generator_lock = experiment.runtime_stack.component(
        Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR
    )
    evaluator_lock = experiment.runtime_stack.component(
        Stage9RuntimeComponentRole.CITATION_EVALUATOR
    )
    if planner_lock.operation != "responses.create":
        raise ValueError("planner operation must remain responses.create")
    if generator_lock.operation != "responses.create":
        raise ValueError("generator operation must remain responses.create")
    if evaluator_lock.operation != "responses.parse":
        raise ValueError("citation evaluator operation must remain responses.parse")

    planner_meter = Stage9MeteredPlannerClient(client=openai_client)
    planner = OpenAIPlannerClient(
        client=planner_meter,
        config=PlannerClientConfig(
            model=planner_lock.model_name,
            max_output_tokens=4_000,
            reasoning_effort=planner_lock.reasoning_effort,
            store=False,
        ),
    )
    citation_evaluator = OpenAISemanticCitationEvaluator(
        client=openai_client,
        model=evaluator_lock.model_name,
    )
    grounded_workflow = create_bounded_grounded_answer_orchestrator(
        client=openai_client,
        model=generator_lock.model_name,
        citation_evaluator=citation_evaluator,
    )
    packed_loop_factory = Stage9PackedResearchLoopFactory(
        experiment=experiment,
        planner_client=planner,
        planner_meter=planner_meter,
        grounded_workflow=grounded_workflow,
    )
    return create_stage9_real_development_runtime(
        experiment=experiment,
        environ=environ,
        repository_root=repository_root,
        packed_loop_factory=packed_loop_factory,
        tavily_client=tavily_client,
        openalex_client=openalex_client,
        epo_client=epo_client,
    )
