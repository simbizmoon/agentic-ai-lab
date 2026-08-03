"""Lifecycle transitions for structured agent plans."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from app.memory.clock import Clock, SystemClock
from app.planning.plan_validator import PlanValidator
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_lifecycle import (
    PlanLifecycleResult,
)


class PlanLifecycleError(RuntimeError):
    """Raised when a plan lifecycle transition is invalid."""


class PlanLifecycleService:
    """Apply validated lifecycle transitions to plans."""

    _TERMINAL_PLAN_STATUSES: ClassVar[
        set[PlanStatus]
    ] = {
        PlanStatus.COMPLETED,
        PlanStatus.FAILED,
        PlanStatus.CANCELLED,
    }

    _SATISFIED_STEP_STATUSES: ClassVar[
        set[PlanStepStatus]
    ] = {
        PlanStepStatus.COMPLETED,
        PlanStepStatus.SKIPPED,
    }

    def __init__(
        self,
        *,
        validator: PlanValidator | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._validator = validator or PlanValidator()
        self._clock = clock or SystemClock()

    @property
    def validator(self) -> PlanValidator:
        """Return the configured plan validator."""

        return self._validator

    def start_plan(
        self,
        plan: Plan,
    ) -> PlanLifecycleResult:
        """Move a draft or ready plan into progress."""

        if plan.status not in {
            PlanStatus.DRAFT,
            PlanStatus.READY,
        }:
            raise PlanLifecycleError(
                "only a draft or ready plan can be started"
            )

        updated_plan = plan.model_copy(
            update={
                "status": PlanStatus.IN_PROGRESS,
                "updated_at": self._validated_now(),
            },
            deep=True,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=[],
        )

    def start_step(
        self,
        plan: Plan,
        *,
        step_id: str,
    ) -> PlanLifecycleResult:
        """Move one ready step into progress."""

        self._require_active_plan(plan)

        if plan.status is not PlanStatus.IN_PROGRESS:
            raise PlanLifecycleError(
                "the plan must be in progress "
                "before starting a step"
            )

        target = self._get_step(
            plan=plan,
            step_id=step_id,
        )

        if target.status is not PlanStepStatus.READY:
            raise PlanLifecycleError(
                f"step {step_id} must be ready "
                "before it can start"
            )

        updated_plan = self._replace_step_status(
            plan=plan,
            step_id=step_id,
            status=PlanStepStatus.IN_PROGRESS,
            plan_status=PlanStatus.IN_PROGRESS,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=[step_id],
        )

    def complete_step(
        self,
        plan: Plan,
        *,
        step_id: str,
    ) -> PlanLifecycleResult:
        """Complete one step and unlock eligible dependents."""

        self._require_active_plan(plan)

        target = self._get_step(
            plan=plan,
            step_id=step_id,
        )

        if target.status is not PlanStepStatus.IN_PROGRESS:
            raise PlanLifecycleError(
                f"step {step_id} must be in progress "
                "before it can complete"
            )

        steps = [
            step.model_copy(deep=True)
            for step in plan.steps
        ]
        changed_step_ids = [step_id]

        for index, step in enumerate(steps):
            if step.step_id == step_id:
                steps[index] = step.model_copy(
                    update={
                        "status": (
                            PlanStepStatus.COMPLETED
                        )
                    },
                    deep=True,
                )
                break

        newly_ready = self._activate_eligible_steps(
            steps
        )
        changed_step_ids.extend(newly_ready)

        plan_status = (
            PlanStatus.COMPLETED
            if self._all_steps_finished(steps)
            else PlanStatus.IN_PROGRESS
        )

        updated_plan = plan.model_copy(
            update={
                "status": plan_status,
                "steps": steps,
                "updated_at": self._validated_now(),
            },
            deep=True,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=changed_step_ids,
        )

    def fail_step(
        self,
        plan: Plan,
        *,
        step_id: str,
    ) -> PlanLifecycleResult:
        """Fail an in-progress step and fail the plan."""

        self._require_active_plan(plan)

        target = self._get_step(
            plan=plan,
            step_id=step_id,
        )

        if target.status is not PlanStepStatus.IN_PROGRESS:
            raise PlanLifecycleError(
                f"step {step_id} must be in progress "
                "before it can fail"
            )

        updated_plan = self._replace_step_status(
            plan=plan,
            step_id=step_id,
            status=PlanStepStatus.FAILED,
            plan_status=PlanStatus.FAILED,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=[step_id],
        )

    def skip_step(
        self,
        plan: Plan,
        *,
        step_id: str,
    ) -> PlanLifecycleResult:
        """Skip a pending or ready step and unlock dependents."""

        self._require_active_plan(plan)

        target = self._get_step(
            plan=plan,
            step_id=step_id,
        )

        if target.status not in {
            PlanStepStatus.PENDING,
            PlanStepStatus.READY,
        }:
            raise PlanLifecycleError(
                f"step {step_id} must be pending or ready "
                "before it can be skipped"
            )

        steps = [
            step.model_copy(deep=True)
            for step in plan.steps
        ]
        changed_step_ids = [step_id]

        for index, step in enumerate(steps):
            if step.step_id == step_id:
                steps[index] = step.model_copy(
                    update={
                        "status": PlanStepStatus.SKIPPED
                    },
                    deep=True,
                )
                break

        newly_ready = self._activate_eligible_steps(
            steps
        )
        changed_step_ids.extend(newly_ready)

        plan_status = (
            PlanStatus.COMPLETED
            if self._all_steps_finished(steps)
            else plan.status
        )

        updated_plan = plan.model_copy(
            update={
                "status": plan_status,
                "steps": steps,
                "updated_at": self._validated_now(),
            },
            deep=True,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=changed_step_ids,
        )

    def cancel_plan(
        self,
        plan: Plan,
    ) -> PlanLifecycleResult:
        """Cancel a non-terminal plan and skip unfinished steps."""

        self._require_active_plan(plan)

        steps: list[PlanStep] = []
        changed_step_ids: list[str] = []

        for step in plan.steps:
            if step.status in {
                PlanStepStatus.PENDING,
                PlanStepStatus.READY,
                PlanStepStatus.IN_PROGRESS,
            }:
                steps.append(
                    step.model_copy(
                        update={
                            "status": (
                                PlanStepStatus.SKIPPED
                            )
                        },
                        deep=True,
                    )
                )
                changed_step_ids.append(
                    step.step_id
                )
            else:
                steps.append(
                    step.model_copy(deep=True)
                )

        updated_plan = plan.model_copy(
            update={
                "status": PlanStatus.CANCELLED,
                "steps": steps,
                "updated_at": self._validated_now(),
            },
            deep=True,
        )

        return self._result(
            plan=updated_plan,
            changed_step_ids=changed_step_ids,
        )

    def _result(
        self,
        *,
        plan: Plan,
        changed_step_ids: list[str],
    ) -> PlanLifecycleResult:
        """Validate and package one lifecycle result."""

        validation = self.validator.validate(plan)

        if not validation.valid:
            error_codes = [
                issue.code.value
                for issue in validation.issues
                if issue.severity.value == "error"
            ]
            raise PlanLifecycleError(
                "lifecycle transition produced an "
                "invalid plan: "
                + ", ".join(error_codes)
            )

        return PlanLifecycleResult(
            plan=plan,
            validation=validation,
            changed_step_ids=changed_step_ids,
        )

    def _replace_step_status(
        self,
        *,
        plan: Plan,
        step_id: str,
        status: PlanStepStatus,
        plan_status: PlanStatus,
    ) -> Plan:
        """Return a copy with one replaced step status."""

        steps = [
            (
                step.model_copy(
                    update={"status": status},
                    deep=True,
                )
                if step.step_id == step_id
                else step.model_copy(deep=True)
            )
            for step in plan.steps
        ]

        return plan.model_copy(
            update={
                "status": plan_status,
                "steps": steps,
                "updated_at": self._validated_now(),
            },
            deep=True,
        )

    @classmethod
    def _activate_eligible_steps(
        cls,
        steps: list[PlanStep],
    ) -> list[str]:
        """Move eligible pending steps into ready state."""

        step_by_id = {
            step.step_id: step
            for step in steps
        }
        changed_step_ids: list[str] = []

        for index, step in enumerate(steps):
            if step.status is not PlanStepStatus.PENDING:
                continue

            dependencies_satisfied = all(
                step_by_id[dependency].status
                in cls._SATISFIED_STEP_STATUSES
                for dependency in step.dependencies
            )

            if dependencies_satisfied:
                steps[index] = step.model_copy(
                    update={
                        "status": PlanStepStatus.READY
                    },
                    deep=True,
                )
                step_by_id[step.step_id] = steps[index]
                changed_step_ids.append(step.step_id)

        return changed_step_ids

    @classmethod
    def _all_steps_finished(
        cls,
        steps: list[PlanStep],
    ) -> bool:
        """Return whether all steps completed or skipped."""

        return all(
            step.status in cls._SATISFIED_STEP_STATUSES
            for step in steps
        )

    @staticmethod
    def _get_step(
        *,
        plan: Plan,
        step_id: str,
    ) -> PlanStep:
        """Return one plan step or raise an error."""

        if not step_id.strip():
            raise PlanLifecycleError(
                "step_id must not be blank"
            )

        for step in plan.steps:
            if step.step_id == step_id:
                return step

        raise PlanLifecycleError(
            f"unknown plan step: {step_id}"
        )

    @classmethod
    def _require_active_plan(
        cls,
        plan: Plan,
    ) -> None:
        """Reject lifecycle operations on terminal plans."""

        if plan.status in cls._TERMINAL_PLAN_STATUSES:
            raise PlanLifecycleError(
                f"plan is already terminal: "
                f"{plan.status.value}"
            )

    def _validated_now(self) -> datetime:
        """Return one timezone-aware UTC clock value."""

        value = self._clock.now()

        if value.tzinfo is None:
            raise PlanLifecycleError(
                "clock must return a timezone-aware datetime"
            )

        if value.utcoffset() != UTC.utcoffset(value):
            raise PlanLifecycleError(
                "clock must return UTC"
            )

        return value
