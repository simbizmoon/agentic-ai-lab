"""Schemas for bounded automatic planning-agent replanning."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
    PlanEvaluationResult,
)
from app.schemas.plan_run import PlanRunResult
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)
from app.schemas.planning_result import PlanningResult


class PlanningAgentLoopStatus(StrEnum):
    """Terminal outcome of an automatic planning loop."""

    GOAL_ACHIEVED = "goal_achieved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    REPLAN_LIMIT_REACHED = "replan_limit_reached"


class PlanningAgentLoopRequest(BaseModel):
    """Configuration for initial planning and replanning."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    initial: PlanningAgentRequest
    maximum_replans: int = Field(
        default=2,
        ge=0,
        le=10,
    )


class PlanningAgentAttempt(BaseModel):
    """One planning, execution, and evaluation attempt."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    attempt_number: int = Field(ge=1)
    planning: PlanningResult
    run: PlanRunResult
    evaluation: PlanEvaluationResult
    source_plan_id: str | None = None

    @model_validator(mode="after")
    def validate_attempt(
        self,
    ) -> PlanningAgentAttempt:
        """Validate attempt-stage consistency."""

        created_plan_id = (
            self.planning.created_plan.plan.plan_id
        )

        if created_plan_id != self.run.plan.plan_id:
            raise ValueError(
                "attempt planning and run plan IDs must match"
            )

        if (
            self.attempt_number == 1
            and self.source_plan_id is not None
        ):
            raise ValueError(
                "initial attempt must not have source_plan_id"
            )

        if (
            self.attempt_number > 1
            and (
                self.source_plan_id is None
                or not self.source_plan_id.strip()
            )
        ):
            raise ValueError(
                "replan attempt requires source_plan_id"
            )

        return self


class PlanningAgentLoopResult(BaseModel):
    """Complete bounded planning-agent loop result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    attempts: list[PlanningAgentAttempt] = Field(
        min_length=1
    )
    status: PlanningAgentLoopStatus

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanningAgentLoopResult:
        """Validate attempt ordering and final outcome."""

        attempt_numbers = [
            attempt.attempt_number
            for attempt in self.attempts
        ]

        if attempt_numbers != list(
            range(1, len(self.attempts) + 1)
        ):
            raise ValueError(
                "attempt numbers must be sequential"
            )

        plan_ids = [
            attempt.run.plan.plan_id
            for attempt in self.attempts
        ]

        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError(
                "every attempt must use a new plan ID"
            )

        final_decision = (
            self.attempts[-1].evaluation.decision
        )

        if (
            self.status
            is PlanningAgentLoopStatus.GOAL_ACHIEVED
            and final_decision
            is not PlanEvaluationDecision.GOAL_ACHIEVED
        ):
            raise ValueError(
                "goal-achieved loop requires successful "
                "final evaluation"
            )

        return self
