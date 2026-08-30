"""Offline integration tests for the Stage 9 packed research loop factory."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.planning.openai_planner_client import OpenAIPlannerClient
from app.research.stage9_packed_research_loop_factory import (
    Stage9PackedResearchLoopFactory,
    Stage9PackedResearchLoopFactoryError,
)
from app.research.stage9_planner_usage_accounting import Stage9MeteredPlannerClient
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    ResearchAgentLoopDecision,
)
from app.schemas.planner_client_config import PlannerClientConfig
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


def _packing() -> RagContextPackingResult:
    request = RagContextPackingRequest(
        candidates=[],
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="stage9-packed-loop-test-v1",
        ),
    )
    return RagContextPackingResult(
        request=request,
        included=[],
        omitted=[],
        usage=RagContextPackingUsage(
            candidate_count=0,
            included_count=0,
            omitted_count=0,
            context_utf8_bytes=0,
            estimated_tokens=0,
        ),
        was_truncated=False,
    )


class PlannerResponses:
    def create(self, **kwargs):
        del kwargs
        output = {
            "reasoning_summary": "Run the only bounded grounded-answer tool.",
            "steps": [
                {
                    "step_id": "grounded-answer-step",
                    "title": "Run bounded grounded answer",
                    "description": "Use only the server-locked packed evidence.",
                    "tool_name": "bounded_grounded_answer",
                    "expected_output": "One bounded grounded answer result",
                    "metadata": {
                        "workflow_request": {"question": "planner replacement"}
                    },
                }
            ],
        }
        return SimpleNamespace(
            output_text=json.dumps(output),
            id="planner-response-001",
            model="gpt-5.6-terra",
            usage=SimpleNamespace(
                input_tokens=10,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens=5,
                output_tokens_details=SimpleNamespace(reasoning_tokens=1),
                total_tokens=15,
            ),
        )


class ControlledWorkflow:
    def __init__(self) -> None:
        self.requests = []

    def run(self, *, request):
        self.requests.append(request)
        return BoundedGroundedAnswerWorkflowResult(
            request=request,
            status=GroundedAnswerWorkflowStatus.GENERATION_FAILED,
            generation_usage=GroundedAnswerGenerationUsage(
                attempts=1,
                recorded_tokens=7,
                elapsed_seconds=0.01,
            ),
            generation_budget_exhausted=False,
            answer=None,
            citation_validation=None,
            abstention_detected=False,
            failure=GroundedAnswerWorkflowFailure(
                stage=GroundedAnswerWorkflowFailureStage.GENERATION,
                code="controlled_terminal_failure",
                safe_message="Controlled terminal failure.",
                retryable=False,
            ),
        )


def _factory():
    meter = Stage9MeteredPlannerClient(
        client=SimpleNamespace(responses=PlannerResponses())
    )
    workflow = ControlledWorkflow()
    planner = OpenAIPlannerClient(
        client=meter,
        config=PlannerClientConfig(
            model="gpt-5.6-terra",
            max_output_tokens=1_000,
            reasoning_effort="low",
            store=False,
        ),
    )
    return (
        Stage9PackedResearchLoopFactory(
            experiment=load_approved_baseline(MANIFEST, REVIEW),
            planner_client=planner,
            planner_meter=meter,
            grounded_workflow=workflow,
        ),
        workflow,
    )


def test_real_planning_pipeline_uses_locked_request_and_counts_planner() -> None:
    factory, workflow = _factory()
    loop = factory.create(case_id="tech-01", packing=_packing())
    result = loop.run(
        request=BoundedResearchAgentLoopRequest(
            goal=(
                "Which NIST AI RMF functions and GAI risk actions are relevant to "
                "a bounded research agent?"
            ),
            allowed_tools=["bounded_grounded_answer"],
            budget=BoundedResearchAgentLoopBudget(
                maximum_rounds=1,
                maximum_tool_calls=1,
                maximum_provider_calls=2,
                maximum_recorded_tokens=100,
                maximum_elapsed_seconds=10.0,
                maximum_external_requests=2,
            ),
        )
    )

    assert result.final_decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED
    assert result.usage.provider_calls == 2
    assert result.usage.external_requests == 2
    assert result.usage.recorded_tokens == 22
    assert len(workflow.requests) == 1
    assert workflow.requests[0].question == result.request.goal
    assert workflow.requests[0].packing == _packing()


def test_blind_holdout_cannot_create_a_loop() -> None:
    factory, _ = _factory()
    with pytest.raises(Stage9PackedResearchLoopFactoryError, match="development"):
        factory.create(case_id="tech-02", packing=_packing())
