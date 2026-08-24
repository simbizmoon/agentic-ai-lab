"""Planning-tool and observation adapters for the Stage 6 grounded workflow."""

from __future__ import annotations

from typing import Protocol

from pydantic import ValidationError

from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerWorkflowRequest,
)
from app.schemas.bounded_research_agent_loop import (
    ResearchAgentObservation,
    ResearchAgentObservationFailure,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.tool import Tool

BOUNDED_GROUNDED_ANSWER_TOOL_NAME = "bounded_grounded_answer"


class GroundedAnswerWorkflowProtocol(Protocol):
    def run(
        self, *, request: GroundedAnswerWorkflowRequest
    ) -> BoundedGroundedAnswerWorkflowResult: ...


class BoundedGroundedAnswerAgentTool(Tool):
    """Expose one already-composed Stage 6 workflow as a planning tool."""

    def __init__(
        self,
        *,
        workflow: GroundedAnswerWorkflowProtocol,
        provider_calls_are_external: bool,
    ) -> None:
        self._workflow = workflow
        self._provider_calls_are_external = provider_calls_are_external

    @property
    def name(self) -> str:
        return BOUNDED_GROUNDED_ANSWER_TOOL_NAME

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        try:
            workflow_request = self._workflow_request(request)
        except (TypeError, ValidationError, ValueError):
            return self._failure(
                code="invalid_workflow_request",
                message="The grounded-answer workflow request is invalid.",
                retryable=False,
            )

        try:
            result = self._workflow.run(request=workflow_request)
        except Exception:  # noqa: BLE001 - do not leak provider or workflow details
            return self._failure(
                code="grounded_workflow_failed",
                message="The bounded grounded-answer workflow failed.",
                retryable=False,
            )
        if not isinstance(result, BoundedGroundedAnswerWorkflowResult):
            return self._failure(
                code="invalid_workflow_result",
                message="The grounded-answer workflow returned an invalid result.",
                retryable=False,
            )

        validation_usage = (
            result.citation_validation.usage
            if result.citation_validation is not None
            else None
        )
        validation_attempts = validation_usage.attempts if validation_usage else 0
        provider_calls = result.generation_usage.attempts + validation_attempts
        recorded_tokens = result.generation_usage.recorded_tokens + (
            validation_usage.recorded_tokens if validation_usage else 0
        )
        elapsed_seconds = result.generation_usage.elapsed_seconds + (
            validation_usage.elapsed_seconds if validation_usage else 0.0
        )
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.SUCCEEDED,
            output=result,
            metadata={
                "provider_calls": provider_calls,
                "recorded_tokens": recorded_tokens,
                "elapsed_seconds": elapsed_seconds,
                "external_requests": (
                    provider_calls if self._provider_calls_are_external else 0
                ),
                "workflow_status": result.status.value,
            },
        )

    @staticmethod
    def _workflow_request(
        request: ToolExecutionRequest,
    ) -> GroundedAnswerWorkflowRequest:
        value = request.arguments.get("workflow_request")
        if value is None:
            metadata = request.arguments.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get("workflow_request")
        if isinstance(value, GroundedAnswerWorkflowRequest):
            return value
        if isinstance(value, dict):
            return GroundedAnswerWorkflowRequest.model_validate(value)
        raise TypeError("workflow_request is required")

    def _failure(
        self, *, code: str, message: str, retryable: bool
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.FAILED,
            error_message=message,
            metadata={"error_code": code, "retryable": retryable},
        )


class GroundedAnswerToolObservationAdapter:
    """Convert exact planning-tool output into a Stage 7 observation and usage."""

    def adapt(
        self, *, observation_id: str, result: ToolExecutionResult
    ) -> tuple[ResearchAgentObservation, ResearchAgentRoundUsage]:
        if result.tool_name != BOUNDED_GROUNDED_ANSWER_TOOL_NAME:
            raise ValueError("tool result is not from bounded_grounded_answer")
        if result.status is ToolExecutionStatus.FAILED:
            return self._failed_observation(
                observation_id=observation_id, result=result
            )
        if not isinstance(result.output, BoundedGroundedAnswerWorkflowResult):
            raise TypeError(
                "successful grounded-answer tool result requires exact output"
            )

        usage = self._usage(result.metadata)
        return (
            ResearchAgentObservation(
                observation_id=observation_id,
                tool_name=result.tool_name,
                status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
                workflow_result=result.output,
            ),
            usage,
        )

    def _failed_observation(
        self, *, observation_id: str, result: ToolExecutionResult
    ) -> tuple[ResearchAgentObservation, ResearchAgentRoundUsage]:
        code = result.metadata.get("error_code")
        retryable = result.metadata.get("retryable")
        if (
            not isinstance(code, str)
            or not code.strip()
            or not isinstance(retryable, bool)
        ):
            raise ValueError(
                "failed grounded-answer result requires safe failure metadata"
            )
        observation = ResearchAgentObservation(
            observation_id=observation_id,
            tool_name=result.tool_name,
            status=ResearchAgentObservationStatus.TOOL_FAILED,
            failure=ResearchAgentObservationFailure(
                code=code,
                safe_message=result.error_message or "Grounded-answer tool failed.",
                retryable=retryable,
            ),
        )
        return observation, ResearchAgentRoundUsage(
            tool_calls=1,
            provider_calls=0,
            recorded_tokens=0,
            elapsed_seconds=0.0,
            external_requests=0,
        )

    @staticmethod
    def _usage(metadata: dict[str, object]) -> ResearchAgentRoundUsage:
        expected = {
            "provider_calls": int,
            "recorded_tokens": int,
            "elapsed_seconds": (int, float),
            "external_requests": int,
        }
        if any(
            isinstance(metadata.get(name), bool)
            or not isinstance(metadata.get(name), value_type)
            for name, value_type in expected.items()
        ):
            raise ValueError("grounded-answer tool usage metadata is invalid")
        return ResearchAgentRoundUsage(
            tool_calls=1,
            provider_calls=metadata["provider_calls"],
            recorded_tokens=metadata["recorded_tokens"],
            elapsed_seconds=float(metadata["elapsed_seconds"]),
            external_requests=metadata["external_requests"],
        )
