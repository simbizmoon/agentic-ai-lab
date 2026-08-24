"""Deterministically map Stage 6 observations to Stage 7 loop decisions."""

from __future__ import annotations

from app.schemas.bounded_grounded_answer_workflow import GroundedAnswerWorkflowStatus
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    ResearchAgentLoopDecision,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationStatus,
)
from app.schemas.evidence_sufficiency_decision import (
    EvidenceSufficiencyDecisionCode,
    EvidenceSufficiencyDecisionResult,
)


class DeterministicEvidenceSufficiencyDecider:
    """Use only validated workflow state, retryability, and loop ceilings."""

    def decide(
        self,
        *,
        observations: list[ResearchAgentObservation],
        usage_after_round: ResearchAgentLoopUsage,
        budget: BoundedResearchAgentLoopBudget,
    ) -> EvidenceSufficiencyDecisionResult:
        if not observations:
            raise ValueError("at least one research observation is required")
        if not all(isinstance(item, ResearchAgentObservation) for item in observations):
            raise TypeError("observations must contain ResearchAgentObservation values")

        statuses = [
            item.workflow_result.status
            for item in observations
            if item.status is ResearchAgentObservationStatus.WORKFLOW_RESULT
            and item.workflow_result is not None
        ]
        if GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE in statuses:
            return self._result(
                decision=ResearchAgentLoopDecision.GOAL_ACHIEVED,
                code=EvidenceSufficiencyDecisionCode.GROUNDED_ANSWER_AVAILABLE,
                rationale="A citation-validated grounded answer is available.",
            )
        if GroundedAnswerWorkflowStatus.ABSTAINED in statuses:
            return self._result(
                decision=ResearchAgentLoopDecision.ABSTAIN,
                code=EvidenceSufficiencyDecisionCode.GROUNDED_ABSTENTION,
                rationale="The grounded workflow explicitly abstained on the available evidence.",
            )
        if self._budget_reached(usage=usage_after_round, budget=budget):
            return self._result(
                decision=ResearchAgentLoopDecision.BUDGET_EXHAUSTED,
                code=EvidenceSufficiencyDecisionCode.LOOP_BUDGET_REACHED,
                rationale="At least one bounded research-loop ceiling has been reached.",
            )

        retryability = self._failure_retryability(observations)
        has_incomplete = GroundedAnswerWorkflowStatus.INCOMPLETE in statuses
        has_validation_failure = (
            GroundedAnswerWorkflowStatus.VALIDATION_FAILED in statuses
        )

        if retryability == {True} or (has_incomplete and not retryability):
            return self._result(
                decision=ResearchAgentLoopDecision.REPLAN,
                code=(
                    EvidenceSufficiencyDecisionCode.RETRYABLE_FAILURE
                    if retryability
                    else EvidenceSufficiencyDecisionCode.WORKFLOW_INCOMPLETE
                ),
                rationale=(
                    "The recorded failure is retryable and loop budget remains."
                    if retryability
                    else "The workflow is incomplete and loop budget remains."
                ),
            )
        if retryability == {False} or has_validation_failure:
            return self._result(
                decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
                code=EvidenceSufficiencyDecisionCode.NONRETRYABLE_FAILURE,
                rationale="The workflow recorded a nonretryable or validation failure.",
            )
        return self._result(
            decision=ResearchAgentLoopDecision.HUMAN_REVIEW,
            code=EvidenceSufficiencyDecisionCode.CONFLICTING_FAILURE_SIGNALS,
            rationale="The observations contain conflicting or unsupported failure signals.",
        )

    @staticmethod
    def _failure_retryability(
        observations: list[ResearchAgentObservation],
    ) -> set[bool]:
        values = {
            item.failure.retryable
            for item in observations
            if item.status is ResearchAgentObservationStatus.TOOL_FAILED
            and item.failure is not None
        }
        values.update(
            item.workflow_result.failure.retryable
            for item in observations
            if item.workflow_result is not None
            and item.workflow_result.failure is not None
        )
        return values

    @staticmethod
    def _budget_reached(
        *, usage: ResearchAgentLoopUsage, budget: BoundedResearchAgentLoopBudget
    ) -> bool:
        return (
            usage.rounds >= budget.maximum_rounds
            or usage.tool_calls >= budget.maximum_tool_calls
            or (
                usage.provider_calls > 0
                and usage.provider_calls >= budget.maximum_provider_calls
            )
            or (
                usage.recorded_tokens > 0
                and usage.recorded_tokens >= budget.maximum_recorded_tokens
            )
            or usage.elapsed_seconds >= budget.maximum_elapsed_seconds
            or (
                usage.external_requests > 0
                and usage.external_requests >= budget.maximum_external_requests
            )
        )

    @staticmethod
    def _result(
        *,
        decision: ResearchAgentLoopDecision,
        code: EvidenceSufficiencyDecisionCode,
        rationale: str,
    ) -> EvidenceSufficiencyDecisionResult:
        return EvidenceSufficiencyDecisionResult(
            decision=decision,
            code=code,
            rationale=rationale,
            replan_recommended=decision is ResearchAgentLoopDecision.REPLAN,
            human_review_recommended=decision is ResearchAgentLoopDecision.HUMAN_REVIEW,
        )
