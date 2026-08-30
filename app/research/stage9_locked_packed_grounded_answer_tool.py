"""Force server-locked Stage 9 evidence into the grounded-answer agent tool."""

from __future__ import annotations

from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
    BoundedGroundedAnswerAgentTool,
    GroundedAnswerWorkflowProtocol,
)
from app.schemas.answer_citation_validation import AnswerCitationValidationBudget
from app.schemas.bounded_grounded_answer_workflow import (
    GroundedAnswerGenerationBudget,
    GroundedAnswerWorkflowRequest,
)
from app.schemas.rag_context_packing import RagContextPackingResult
from app.schemas.tool_execution import ToolExecutionRequest, ToolExecutionResult
from app.tools.tool import Tool


class Stage9LockedPackedGroundedAnswerTool(Tool):
    """Ignore planner-authored arguments and inject one immutable workflow request."""

    def __init__(
        self,
        *,
        workflow: GroundedAnswerWorkflowProtocol,
        workflow_request: GroundedAnswerWorkflowRequest,
    ) -> None:
        if not isinstance(workflow_request, GroundedAnswerWorkflowRequest):
            raise TypeError("workflow_request must be GroundedAnswerWorkflowRequest")
        self._workflow_request = workflow_request
        self._delegate = BoundedGroundedAnswerAgentTool(
            workflow=workflow,
            provider_calls_are_external=True,
        )

    @property
    def name(self) -> str:
        return BOUNDED_GROUNDED_ANSWER_TOOL_NAME

    @property
    def workflow_request(self) -> GroundedAnswerWorkflowRequest:
        return self._workflow_request

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        if not isinstance(request, ToolExecutionRequest):
            raise TypeError("request must be ToolExecutionRequest")
        locked = ToolExecutionRequest(
            step_id=request.step_id,
            description=request.description,
            arguments={"workflow_request": self._workflow_request},
        )
        return self._delegate.execute(locked)


def create_stage9_locked_workflow_request(
    *,
    question: str,
    packing: RagContextPackingResult,
) -> GroundedAnswerWorkflowRequest:
    """Create the fixed per-case request under the Stage 9 recorded-token ceiling."""

    return GroundedAnswerWorkflowRequest(
        question=question.strip(),
        packing=packing,
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=10_000,
            maximum_elapsed_seconds=300.0,
        ),
        citation_validation_budget=AnswerCitationValidationBudget(
            maximum_statements=8,
            maximum_pairs=8,
            maximum_attempts=8,
            maximum_recorded_tokens=20_000,
            maximum_elapsed_seconds=300.0,
        ),
    )
