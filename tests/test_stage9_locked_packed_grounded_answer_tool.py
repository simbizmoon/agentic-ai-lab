"""Offline tests for server-locked Stage 9 grounded tool inputs."""

from __future__ import annotations

from app.research.stage9_locked_packed_grounded_answer_tool import (
    Stage9LockedPackedGroundedAnswerTool,
    create_stage9_locked_workflow_request,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.tool_execution import ToolExecutionRequest, ToolExecutionStatus


def _packing() -> RagContextPackingResult:
    request = RagContextPackingRequest(
        candidates=[],
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="stage9-locked-tool-test-v1",
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


class RecordingWorkflow:
    def __init__(self) -> None:
        self.requests = []

    def run(self, *, request):
        self.requests.append(request)
        return BoundedGroundedAnswerWorkflowResult(
            request=request,
            status=GroundedAnswerWorkflowStatus.GENERATION_FAILED,
            generation_usage=GroundedAnswerGenerationUsage(
                attempts=1,
                recorded_tokens=0,
                elapsed_seconds=0.01,
            ),
            generation_budget_exhausted=False,
            answer=None,
            citation_validation=None,
            abstention_detected=False,
            failure=GroundedAnswerWorkflowFailure(
                stage=GroundedAnswerWorkflowFailureStage.GENERATION,
                code="controlled_failure",
                safe_message="Controlled offline failure.",
                retryable=False,
            ),
        )


def test_forces_locked_request_over_planner_authored_arguments() -> None:
    workflow = RecordingWorkflow()
    locked = create_stage9_locked_workflow_request(
        question="Which NIST functions are relevant?",
        packing=_packing(),
    )
    tool = Stage9LockedPackedGroundedAnswerTool(
        workflow=workflow,
        workflow_request=locked,
    )

    result = tool.execute(
        ToolExecutionRequest(
            step_id="planner-step-001",
            description="Run grounded research",
            arguments={
                "workflow_request": {"question": "malicious replacement"},
                "untrusted_planner_field": "ignored",
            },
        )
    )

    assert result.status is ToolExecutionStatus.SUCCEEDED
    assert workflow.requests == [locked]
    assert result.output.request == locked
    assert result.metadata["external_requests"] == 1


def test_locked_budgets_fit_the_case_recorded_token_ceiling() -> None:
    request = create_stage9_locked_workflow_request(
        question="Which NIST functions are relevant?",
        packing=_packing(),
    )
    assert request.generation_budget.maximum_attempts == 1
    assert request.generation_budget.maximum_recorded_tokens == 10_000
    assert request.citation_validation_budget.maximum_attempts == 8
    assert request.citation_validation_budget.maximum_recorded_tokens == 20_000
    assert (
        request.generation_budget.maximum_recorded_tokens
        + request.citation_validation_budget.maximum_recorded_tokens
        == 30_000
    )


def test_rejects_blank_question_before_any_workflow_call() -> None:
    try:
        create_stage9_locked_workflow_request(question=" ", packing=_packing())
    except ValueError as error:
        assert "question" in str(error)
    else:
        raise AssertionError("blank question must fail")
