"""Deterministic selection of executable plan steps."""

from __future__ import annotations

from app.planning.plan_validator import PlanValidator
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStepStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleRequest,
    PlanScheduleResult,
)


class PlanScheduler:
    """Select ready plan steps without mutating the plan."""

    def __init__(
        self,
        *,
        validator: PlanValidator | None = None,
    ) -> None:
        self._validator = validator or PlanValidator()

    @property
    def validator(self) -> PlanValidator:
        """Return the configured plan validator."""

        return self._validator

    def schedule(
        self,
        *,
        plan: Plan,
        request: PlanScheduleRequest | None = None,
    ) -> PlanScheduleResult:
        """Select the next executable plan steps."""

        options = request or PlanScheduleRequest()

        ready_step_ids = [
            step.step_id
            for step in plan.steps
            if step.status is PlanStepStatus.READY
        ]
        active_step_ids = [
            step.step_id
            for step in plan.steps
            if step.status
            is PlanStepStatus.IN_PROGRESS
        ]

        if plan.status is not PlanStatus.IN_PROGRESS:
            return PlanScheduleResult(
                selected_step_ids=[],
                ready_step_ids=ready_step_ids,
                active_step_ids=active_step_ids,
                reason=(
                    PlanScheduleReason
                    .PLAN_NOT_IN_PROGRESS
                ),
            )

        validation = self.validator.validate(plan)

        if not validation.valid:
            return PlanScheduleResult(
                selected_step_ids=[],
                ready_step_ids=ready_step_ids,
                active_step_ids=active_step_ids,
                reason=PlanScheduleReason.PLAN_INVALID,
            )

        if (
            active_step_ids
            and not options.allow_new_steps_while_active
        ):
            return PlanScheduleResult(
                selected_step_ids=[],
                ready_step_ids=ready_step_ids,
                active_step_ids=active_step_ids,
                reason=(
                    PlanScheduleReason
                    .ACTIVE_STEP_EXISTS
                ),
            )

        if not ready_step_ids:
            return PlanScheduleResult(
                selected_step_ids=[],
                ready_step_ids=[],
                active_step_ids=active_step_ids,
                reason=PlanScheduleReason.NO_READY_STEPS,
            )

        ready_set = set(ready_step_ids)
        ordered_ready_step_ids = [
            step_id
            for step_id in validation.execution_order
            if step_id in ready_set
        ]

        selection_limit = (
            options.maximum_selected_steps
            if options.allow_parallel_steps
            else 1
        )

        selected_step_ids = ordered_ready_step_ids[
            :selection_limit
        ]

        return PlanScheduleResult(
            selected_step_ids=selected_step_ids,
            ready_step_ids=ordered_ready_step_ids,
            active_step_ids=active_step_ids,
            reason=PlanScheduleReason.STEPS_SELECTED,
        )
