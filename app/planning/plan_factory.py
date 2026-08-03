"""Factory for materializing validated agent plans."""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.clock import Clock, SystemClock
from app.planning.plan_id_generator import (
    PlanIdGenerator,
    UuidPlanIdGenerator,
)
from app.planning.plan_validator import PlanValidator
from app.schemas.created_plan import CreatedPlan
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_request import (
    PlanCreationRequest,
)


class PlanFactoryError(RuntimeError):
    """Raised when an agent plan cannot be materialized."""


class PlanFactory:
    """Create initialized and validated plans."""

    def __init__(
        self,
        *,
        validator: PlanValidator | None = None,
        clock: Clock | None = None,
        id_generator: PlanIdGenerator | None = None,
    ) -> None:
        self._validator = validator or PlanValidator()
        self._clock = clock or SystemClock()
        self._id_generator = (
            id_generator or UuidPlanIdGenerator()
        )

    @property
    def validator(self) -> PlanValidator:
        """Return the configured plan validator."""

        return self._validator

    def create(
        self,
        *,
        request: PlanCreationRequest,
        steps: list[PlanStepDraft],
    ) -> CreatedPlan:
        """Materialize one initialized plan."""

        if not steps:
            raise PlanFactoryError(
                "a plan requires at least one step"
            )

        if len(steps) > request.maximum_steps:
            raise PlanFactoryError(
                "plan exceeds maximum_steps"
            )

        step_ids = [
            step.step_id
            for step in steps
        ]

        if len(step_ids) != len(set(step_ids)):
            raise PlanFactoryError(
                "plan step IDs must be unique"
            )

        known_step_ids = set(step_ids)

        for step in steps:
            unknown_dependencies = (
                set(step.dependencies)
                - known_step_ids
            )

            if unknown_dependencies:
                unknown_text = ", ".join(
                    sorted(unknown_dependencies)
                )
                raise PlanFactoryError(
                    "step dependencies reference "
                    f"unknown steps: {unknown_text}"
                )

            if (
                request.require_tool_for_each_step
                and step.tool_name is None
            ):
                raise PlanFactoryError(
                    f"step {step.step_id} requires a tool"
                )

            if (
                step.tool_name is not None
                and step.tool_name
                not in request.available_tools
            ):
                raise PlanFactoryError(
                    f"step {step.step_id} uses unavailable "
                    f"tool: {step.tool_name}"
                )

        now = self._validated_now()
        plan_id = self._id_generator.generate()

        if not plan_id.strip():
            raise PlanFactoryError(
                "plan ID generator returned a blank ID"
            )

        materialized_steps = self._materialize_steps(
            steps
        )

        plan = Plan(
            plan_id=plan_id,
            goal=request.goal,
            status=PlanStatus.DRAFT,
            steps=materialized_steps,
            created_at=now,
            updated_at=now,
            metadata={
                **request.metadata,
                "constraints": list(
                    request.constraints
                ),
                "available_tools": list(
                    request.available_tools
                ),
                "allow_parallel_steps": (
                    request.allow_parallel_steps
                ),
            },
        )

        validation = self.validator.validate(plan)

        return CreatedPlan(
            plan=plan,
            validation=validation,
        )

    @staticmethod
    def _materialize_steps(
        drafts: list[PlanStepDraft],
    ) -> list[PlanStep]:
        """Create PlanStep values with initial statuses."""

        return [
            PlanStep(
                step_id=draft.step_id,
                title=draft.title,
                description=draft.description,
                dependencies=list(
                    draft.dependencies
                ),
                status=(
                    PlanStepStatus.READY
                    if not draft.dependencies
                    else PlanStepStatus.PENDING
                ),
                tool_name=draft.tool_name,
                expected_output=draft.expected_output,
                metadata=dict(draft.metadata),
            )
            for draft in drafts
        ]

    def _validated_now(self) -> datetime:
        """Return one timezone-aware UTC clock value."""

        value = self._clock.now()

        if value.tzinfo is None:
            raise PlanFactoryError(
                "clock must return a timezone-aware datetime"
            )

        if value.utcoffset() != UTC.utcoffset(value):
            raise PlanFactoryError(
                "clock must return UTC"
            )

        return value
