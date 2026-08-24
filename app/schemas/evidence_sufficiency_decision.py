"""Contracts for deterministic Stage 7 evidence-sufficiency decisions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.bounded_research_agent_loop import ResearchAgentLoopDecision


class EvidenceSufficiencyDecisionCode(StrEnum):
    GROUNDED_ANSWER_AVAILABLE = "grounded_answer_available"
    GROUNDED_ABSTENTION = "grounded_abstention"
    LOOP_BUDGET_REACHED = "loop_budget_reached"
    WORKFLOW_INCOMPLETE = "workflow_incomplete"
    RETRYABLE_FAILURE = "retryable_failure"
    NONRETRYABLE_FAILURE = "nonretryable_failure"
    CONFLICTING_FAILURE_SIGNALS = "conflicting_failure_signals"


class EvidenceSufficiencyDecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    decision: ResearchAgentLoopDecision
    code: EvidenceSufficiencyDecisionCode
    rationale: str
    replan_recommended: bool
    human_review_recommended: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if not self.rationale.strip() or self.rationale != self.rationale.strip():
            raise ValueError("decision rationale must be normalized and nonblank")
        if self.replan_recommended != (
            self.decision is ResearchAgentLoopDecision.REPLAN
        ):
            raise ValueError("replan recommendation must match decision")
        if self.human_review_recommended != (
            self.decision is ResearchAgentLoopDecision.HUMAN_REVIEW
        ):
            raise ValueError("human-review recommendation must match decision")
        return self
