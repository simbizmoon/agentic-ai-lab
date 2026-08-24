"""Provider-neutral contracts for a bounded single research-agent loop."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerWorkflowStatus,
)


class ResearchAgentLoopDecision(StrEnum):
    CONTINUE = "continue"
    REPLAN = "replan"
    GOAL_ACHIEVED = "goal_achieved"
    ABSTAIN = "abstain"
    HUMAN_REVIEW = "human_review"
    TERMINAL_FAILURE = "terminal_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ResearchAgentTerminationReason(StrEnum):
    GOAL_ACHIEVED = "goal_achieved"
    ABSTAINED = "abstained"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    TERMINAL_FAILURE = "terminal_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ResearchAgentObservationStatus(StrEnum):
    WORKFLOW_RESULT = "workflow_result"
    TOOL_FAILED = "tool_failed"


class BoundedResearchAgentLoopBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_rounds: int = Field(ge=1, le=100)
    maximum_tool_calls: int = Field(ge=1, le=1000)
    maximum_provider_calls: int = Field(ge=0, le=1000)
    maximum_recorded_tokens: int = Field(ge=0, le=10_000_000)
    maximum_elapsed_seconds: float = Field(gt=0.0, le=86_400.0)
    maximum_external_requests: int = Field(ge=0, le=10_000)

    @field_validator("maximum_elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("maximum_elapsed_seconds must be finite")
        return value


class BoundedResearchAgentLoopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    goal: str
    constraints: list[str] = Field(default_factory=list, max_length=100)
    allowed_tools: list[str] = Field(min_length=1, max_length=100)
    budget: BoundedResearchAgentLoopBudget

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        for field_name, values in (
            ("constraints", self.constraints),
            ("allowed_tools", self.allowed_tools),
        ):
            if any(not value.strip() or value != value.strip() for value in values):
                raise ValueError(
                    f"{field_name} must contain normalized nonblank values"
                )
            if len(values) != len({value.casefold() for value in values}):
                raise ValueError(f"{field_name} must be unique case-insensitively")
        if not self.goal.strip() or self.goal != self.goal.strip():
            raise ValueError("research goal must be normalized and nonblank")
        return self


class ResearchAgentObservationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    code: str = Field(min_length=1, max_length=200)
    safe_message: str = Field(min_length=1, max_length=2000)
    retryable: bool

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        for name in ("code", "safe_message"):
            value = getattr(self, name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be normalized and nonblank")
        return self


class ResearchAgentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    observation_id: str
    tool_name: str
    status: ResearchAgentObservationStatus
    workflow_result: BoundedGroundedAnswerWorkflowResult | None = None
    failure: ResearchAgentObservationFailure | None = None

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        for name in ("observation_id", "tool_name"):
            value = getattr(self, name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be normalized and nonblank")
        if self.status is ResearchAgentObservationStatus.WORKFLOW_RESULT:
            if self.workflow_result is None or self.failure is not None:
                raise ValueError("workflow observation requires only workflow_result")
        elif self.failure is None or self.workflow_result is not None:
            raise ValueError("failed observation requires only failure")
        return self


class ResearchAgentRoundUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tool_calls: int = Field(ge=0)
    provider_calls: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0.0)
    external_requests: int = Field(ge=0)

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("elapsed_seconds must be finite")
        return value


class ResearchAgentLoopRound(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    round_number: int = Field(ge=1)
    plan_id: str
    observations: list[ResearchAgentObservation] = Field(
        default_factory=list, max_length=100
    )
    decision: ResearchAgentLoopDecision
    rationale: str
    usage: ResearchAgentRoundUsage

    @model_validator(mode="after")
    def validate_round(self) -> Self:
        for name in ("plan_id", "rationale"):
            value = getattr(self, name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be normalized and nonblank")
        observation_ids = [item.observation_id for item in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("observation IDs must be unique within a round")
        if self.usage.tool_calls != len(self.observations):
            raise ValueError("round tool_calls must match observations")
        return self


class ResearchAgentLoopUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    rounds: int = Field(ge=1)
    tool_calls: int = Field(ge=0)
    provider_calls: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0.0)
    external_requests: int = Field(ge=0)


class BoundedResearchAgentLoopResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: BoundedResearchAgentLoopRequest
    rounds: list[ResearchAgentLoopRound] = Field(min_length=1, max_length=100)
    final_decision: ResearchAgentLoopDecision
    termination_reason: ResearchAgentTerminationReason
    usage: ResearchAgentLoopUsage
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        numbers = [item.round_number for item in self.rounds]
        if numbers != list(range(1, len(self.rounds) + 1)):
            raise ValueError("research loop round numbers must be sequential")
        plan_ids = [item.plan_id for item in self.rounds]
        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError("every research loop round requires a new plan ID")
        observation_ids = [
            observation.observation_id
            for item in self.rounds
            for observation in item.observations
        ]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("observation IDs must be unique across the loop")
        allowed = {value.casefold() for value in self.request.allowed_tools}
        if any(
            observation.tool_name.casefold() not in allowed
            for round_item in self.rounds
            for observation in round_item.observations
        ):
            raise ValueError("research observation used a non-allowed tool")
        if self.final_decision is not self.rounds[-1].decision:
            raise ValueError("final decision must match the last round")

        expected_usage = ResearchAgentLoopUsage(
            rounds=len(self.rounds),
            tool_calls=sum(item.usage.tool_calls for item in self.rounds),
            provider_calls=sum(item.usage.provider_calls for item in self.rounds),
            recorded_tokens=sum(item.usage.recorded_tokens for item in self.rounds),
            elapsed_seconds=sum(item.usage.elapsed_seconds for item in self.rounds),
            external_requests=sum(item.usage.external_requests for item in self.rounds),
        )
        if self.usage != expected_usage:
            raise ValueError("aggregate loop usage must match round usage")
        self._validate_budget()
        self._validate_terminal_mapping()
        self._validate_decision_evidence()
        if self.trace_id is not None and (
            not self.trace_id.strip() or self.trace_id != self.trace_id.strip()
        ):
            raise ValueError("trace_id must be normalized when supplied")
        return self

    def _validate_budget(self) -> None:
        budget = self.request.budget
        exceeded = (
            self.usage.rounds > budget.maximum_rounds
            or self.usage.tool_calls > budget.maximum_tool_calls
            or self.usage.provider_calls > budget.maximum_provider_calls
            or self.usage.recorded_tokens > budget.maximum_recorded_tokens
            or self.usage.elapsed_seconds > budget.maximum_elapsed_seconds
            or self.usage.external_requests > budget.maximum_external_requests
        )
        if (
            exceeded
            and self.final_decision is not ResearchAgentLoopDecision.BUDGET_EXHAUSTED
        ):
            raise ValueError("over-budget loop must terminate as budget_exhausted")
        if self.final_decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED:
            reached = (
                self.usage.rounds >= budget.maximum_rounds
                or self.usage.tool_calls >= budget.maximum_tool_calls
                or self.usage.provider_calls >= budget.maximum_provider_calls
                or self.usage.recorded_tokens >= budget.maximum_recorded_tokens
                or self.usage.elapsed_seconds >= budget.maximum_elapsed_seconds
                or self.usage.external_requests >= budget.maximum_external_requests
            )
            if not reached:
                raise ValueError("budget_exhausted requires a reached loop ceiling")

    def _validate_terminal_mapping(self) -> None:
        mapping = {
            ResearchAgentLoopDecision.GOAL_ACHIEVED: ResearchAgentTerminationReason.GOAL_ACHIEVED,
            ResearchAgentLoopDecision.ABSTAIN: ResearchAgentTerminationReason.ABSTAINED,
            ResearchAgentLoopDecision.HUMAN_REVIEW: ResearchAgentTerminationReason.HUMAN_REVIEW_REQUIRED,
            ResearchAgentLoopDecision.TERMINAL_FAILURE: ResearchAgentTerminationReason.TERMINAL_FAILURE,
            ResearchAgentLoopDecision.BUDGET_EXHAUSTED: ResearchAgentTerminationReason.BUDGET_EXHAUSTED,
        }
        if self.final_decision not in mapping:
            raise ValueError("research loop result requires a terminal final decision")
        if self.termination_reason is not mapping[self.final_decision]:
            raise ValueError("termination reason must match final decision")

    def _validate_decision_evidence(self) -> None:
        workflow_statuses = [
            observation.workflow_result.status
            for observation in self.rounds[-1].observations
            if observation.workflow_result is not None
        ]
        if (
            self.final_decision is ResearchAgentLoopDecision.GOAL_ACHIEVED
            and GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE not in workflow_statuses
        ):
            raise ValueError("goal_achieved requires an available grounded answer")
        if (
            self.final_decision is ResearchAgentLoopDecision.ABSTAIN
            and GroundedAnswerWorkflowStatus.ABSTAINED not in workflow_statuses
        ):
            raise ValueError("abstain requires an abstained grounded workflow")
