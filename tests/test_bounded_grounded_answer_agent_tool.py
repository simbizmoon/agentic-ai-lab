"""Offline tests for Stage 6 grounded-workflow agent adapters."""

from __future__ import annotations

from typing import Any

import pytest

from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import BoundedAnswerCitationVerifier
from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
    BoundedGroundedAnswerAgentTool,
    GroundedAnswerToolObservationAdapter,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationBudget,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import ResearchAgentObservationStatus
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import ToolRegistry


def _request() -> GroundedAnswerWorkflowRequest:
    packing_request = RagContextPackingRequest(
        candidates=[],
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="stage7-step3-offline-v1",
        ),
    )
    return GroundedAnswerWorkflowRequest(
        question="What is supported?",
        packing=RagContextPackingResult(
            request=packing_request,
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
        ),
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
        citation_validation_budget=AnswerCitationValidationBudget(
            maximum_statements=5,
            maximum_pairs=5,
            maximum_attempts=5,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
    )


class Evaluator:
    def evaluate(self, **values: Any) -> SemanticCitationEvaluationResult:
        raise AssertionError(f"empty evidence must not be evaluated: {values}")


def _result() -> BoundedGroundedAnswerWorkflowResult:
    request = _request()
    context = build_rag_context([])
    answer = GroundedAnswerResult(
        question=request.question,
        answer="The supplied evidence is insufficient.",
        citations=[],
        cited_ids=[],
        response_id="response-001",
        model_name="controlled-local-generator",
        evidence_available=False,
    )
    validation = BoundedAnswerCitationVerifier(evaluator=Evaluator()).verify(
        request=AnswerCitationValidationRequest(
            question=request.question,
            answer=answer.answer,
            context=context,
            evidence_retrievals=[],
            citation_required=False,
            budget=request.citation_validation_budget,
            response_id=answer.response_id,
            model_name=answer.model_name,
        )
    )
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.ABSTAINED,
        generation_usage=GroundedAnswerGenerationUsage(
            attempts=1, recorded_tokens=7, elapsed_seconds=0.02
        ),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=True,
    )


class Workflow:
    def __init__(self, result: object | None = None, *, raises: bool = False) -> None:
        self.result = _result() if result is None else result
        self.raises = raises
        self.requests: list[GroundedAnswerWorkflowRequest] = []

    def run(self, *, request: GroundedAnswerWorkflowRequest) -> object:
        self.requests.append(request)
        if self.raises:
            raise RuntimeError("secret provider detail")
        return self.result


def _execution_request(value: object | None = None) -> ToolExecutionRequest:
    arguments = {} if value is None else {"workflow_request": value}
    return ToolExecutionRequest(
        step_id="step-001", description="Run bounded research", arguments=arguments
    )


def test_tool_is_registerable_under_stable_name() -> None:
    tool = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(), provider_calls_are_external=False
    )
    registry = ToolRegistry()
    registry.register(tool)
    assert tool.name == BOUNDED_GROUNDED_ANSWER_TOOL_NAME
    assert registry.require(BOUNDED_GROUNDED_ANSWER_TOOL_NAME) is tool


@pytest.mark.parametrize("as_dict", [False, True])
def test_tool_executes_exact_workflow_request_and_preserves_result(
    as_dict: bool,
) -> None:
    workflow = Workflow()
    tool = BoundedGroundedAnswerAgentTool(
        workflow=workflow, provider_calls_are_external=True
    )
    request = _request()
    value = request.model_dump(mode="python") if as_dict else request
    execution = tool.execute(_execution_request(value))

    assert execution.status is ToolExecutionStatus.SUCCEEDED
    assert execution.output == workflow.result
    assert workflow.requests == [request]
    assert execution.metadata == {
        "provider_calls": 1,
        "recorded_tokens": 7,
        "elapsed_seconds": 0.02,
        "external_requests": 1,
        "workflow_status": "abstained",
    }


def test_tool_accepts_plan_executor_metadata_shape() -> None:
    workflow = Workflow()
    tool = BoundedGroundedAnswerAgentTool(
        workflow=workflow, provider_calls_are_external=False
    )
    execution = tool.execute(
        ToolExecutionRequest(
            step_id="step-001",
            description="Run bounded research",
            arguments={"metadata": {"workflow_request": _request()}},
        )
    )
    assert execution.status is ToolExecutionStatus.SUCCEEDED
    assert execution.metadata["external_requests"] == 0


@pytest.mark.parametrize("value", [None, "invalid", {}, {"question": "missing"}])
def test_tool_returns_safe_failure_for_invalid_request(value: object | None) -> None:
    result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(), provider_calls_are_external=True
    ).execute(_execution_request(value))
    assert result.status is ToolExecutionStatus.FAILED
    assert result.metadata == {
        "error_code": "invalid_workflow_request",
        "retryable": False,
    }


def test_tool_contains_workflow_exception_without_leaking_detail() -> None:
    result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(raises=True), provider_calls_are_external=True
    ).execute(_execution_request(_request()))
    assert result.status is ToolExecutionStatus.FAILED
    assert "secret" not in (result.error_message or "")
    assert result.metadata["error_code"] == "grounded_workflow_failed"


def test_tool_rejects_noncontract_workflow_output() -> None:
    result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(result={"status": "abstained"}),
        provider_calls_are_external=False,
    ).execute(_execution_request(_request()))
    assert result.status is ToolExecutionStatus.FAILED
    assert result.metadata["error_code"] == "invalid_workflow_result"


def test_observation_adapter_preserves_exact_result_and_usage() -> None:
    tool_result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(), provider_calls_are_external=False
    ).execute(_execution_request(_request()))
    observation, usage = GroundedAnswerToolObservationAdapter().adapt(
        observation_id="observation-001", result=tool_result
    )
    assert observation.status is ResearchAgentObservationStatus.WORKFLOW_RESULT
    assert observation.workflow_result == tool_result.output
    assert usage.tool_calls == 1
    assert usage.provider_calls == 1
    assert usage.recorded_tokens == 7
    assert usage.external_requests == 0


def test_observation_adapter_preserves_safe_tool_failure() -> None:
    tool_result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(raises=True), provider_calls_are_external=True
    ).execute(_execution_request(_request()))
    observation, usage = GroundedAnswerToolObservationAdapter().adapt(
        observation_id="observation-failed", result=tool_result
    )
    assert observation.status is ResearchAgentObservationStatus.TOOL_FAILED
    assert observation.failure is not None
    assert observation.failure.code == "grounded_workflow_failed"
    assert usage.tool_calls == 1
    assert usage.provider_calls == 0


def test_observation_adapter_rejects_wrong_tool_and_invalid_success_output() -> None:
    adapter = GroundedAnswerToolObservationAdapter()
    with pytest.raises(ValueError, match="not from"):
        adapter.adapt(
            observation_id="observation-001",
            result=ToolExecutionResult(
                tool_name="other", status=ToolExecutionStatus.SUCCEEDED, output={}
            ),
        )
    with pytest.raises(TypeError, match="requires exact output"):
        adapter.adapt(
            observation_id="observation-001",
            result=ToolExecutionResult(
                tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
                status=ToolExecutionStatus.SUCCEEDED,
                output={},
            ),
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {
            "provider_calls": True,
            "recorded_tokens": 0,
            "elapsed_seconds": 0.0,
            "external_requests": 0,
        },
        {
            "provider_calls": 0,
            "recorded_tokens": -1,
            "elapsed_seconds": 0.0,
            "external_requests": 0,
        },
    ],
)
def test_observation_adapter_rejects_invalid_usage_metadata(
    metadata: dict[str, object],
) -> None:
    with pytest.raises((ValueError, TypeError)):
        GroundedAnswerToolObservationAdapter().adapt(
            observation_id="observation-001",
            result=ToolExecutionResult(
                tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
                status=ToolExecutionStatus.SUCCEEDED,
                output=_result(),
                metadata=metadata,
            ),
        )


def test_adapter_contract_adds_no_quality_ranking_or_legal_fields() -> None:
    forbidden = {
        "quality_score",
        "authority_score",
        "winner",
        "rank",
        "novelty",
        "legal_conclusion",
    }
    result = BoundedGroundedAnswerAgentTool(
        workflow=Workflow(), provider_calls_are_external=False
    ).execute(_execution_request(_request()))
    assert forbidden.isdisjoint(result.metadata)
