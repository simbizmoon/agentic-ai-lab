"""Result schemas for the integrated planning agent pipeline."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.plan import PlanStatus
from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
    PlanEvaluationResult,
)
from app.schemas.plan_run import PlanRunResult
from app.schemas.planning_result import PlanningResult


class PlanningAgentResult(BaseModel):
    """Complete planning, execution, and evaluation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    planning: PlanningResult
    run: PlanRunResult
    evaluation: PlanEvaluationResult

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanningAgentResult:
        """Validate cross-stage pipeline consistency."""

        created_plan_id = (
            self.planning.created_plan.plan.plan_id
        )
        executed_plan_id = self.run.plan.plan_id

        if created_plan_id != executed_plan_id:
            raise ValueError(
                "planning and run results must reference "
                "the same plan"
            )

        if (
            self.evaluation.decision
            is PlanEvaluationDecision.GOAL_ACHIEVED
            and self.run.plan.status
            is not PlanStatus.COMPLETED
        ):
            raise ValueError(
                "goal achieved requires a completed plan"
            )

        known_step_ids = {
            step.step_id
            for step in self.run.plan.steps
        }

        if not set(
            self.evaluation.failed_step_ids
        ).issubset(known_step_ids):
            raise ValueError(
                "evaluation failed steps must reference "
                "the executed plan"
            )

        if not set(
            self.evaluation.incomplete_step_ids
        ).issubset(known_step_ids):
            raise ValueError(
                "evaluation incomplete steps must reference "
                "the executed plan"
            )

        return self
