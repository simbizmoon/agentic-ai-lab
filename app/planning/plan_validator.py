"""Deterministic structural and lifecycle validation for plans."""

from __future__ import annotations

from collections import deque

from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStepStatus,
)
from app.schemas.plan_validation import (
    PlanValidationCode,
    PlanValidationIssue,
    PlanValidationResult,
    PlanValidationSeverity,
)


class PlanValidator:
    """Validate plan dependencies, order, and lifecycle state."""

    def validate(
        self,
        plan: Plan,
    ) -> PlanValidationResult:
        """Return all deterministic findings for one plan."""

        issues: list[PlanValidationIssue] = []

        execution_order = self._topological_order(plan)

        if execution_order is None:
            issues.append(
                PlanValidationIssue(
                    code=(
                        PlanValidationCode
                        .CIRCULAR_DEPENDENCY
                    ),
                    severity=(
                        PlanValidationSeverity.ERROR
                    ),
                    message=(
                        "The plan contains a circular "
                        "step dependency."
                    ),
                    related_step_ids=[
                        step.step_id
                        for step in plan.steps
                    ],
                )
            )
            execution_order = []
        else:
            issues.extend(
                self._dependency_order_issues(
                    plan=plan,
                    execution_order=execution_order,
                )
            )

        issues.extend(
            self._step_status_issues(plan)
        )
        issues.extend(
            self._plan_status_issues(plan)
        )

        has_errors = any(
            issue.severity
            is PlanValidationSeverity.ERROR
            for issue in issues
        )

        return PlanValidationResult(
            valid=not has_errors,
            issues=issues,
            execution_order=execution_order,
        )

    @staticmethod
    def _topological_order(
        plan: Plan,
    ) -> list[str] | None:
        """Return deterministic dependency order or None."""

        step_ids = [
            step.step_id
            for step in plan.steps
        ]
        original_index = {
            step_id: index
            for index, step_id in enumerate(step_ids)
        }

        indegree = {
            step.step_id: len(step.dependencies)
            for step in plan.steps
        }
        dependents: dict[str, list[str]] = {
            step_id: []
            for step_id in step_ids
        }

        for step in plan.steps:
            for dependency in step.dependencies:
                dependents[dependency].append(
                    step.step_id
                )

        for values in dependents.values():
            values.sort(
                key=original_index.__getitem__
            )

        ready = deque(
            step_id
            for step_id in step_ids
            if indegree[step_id] == 0
        )
        order: list[str] = []

        while ready:
            step_id = ready.popleft()
            order.append(step_id)

            newly_ready: list[str] = []

            for dependent in dependents[step_id]:
                indegree[dependent] -= 1

                if indegree[dependent] == 0:
                    newly_ready.append(dependent)

            newly_ready.sort(
                key=original_index.__getitem__
            )
            ready.extend(newly_ready)

        if len(order) != len(step_ids):
            return None

        return order

    @staticmethod
    def _dependency_order_issues(
        *,
        plan: Plan,
        execution_order: list[str],
    ) -> list[PlanValidationIssue]:
        """Report source-list order that violates dependencies."""

        listed_index = {
            step.step_id: index
            for index, step in enumerate(plan.steps)
        }
        execution_index = {
            step_id: index
            for index, step_id in enumerate(
                execution_order
            )
        }

        issues: list[PlanValidationIssue] = []

        for step in plan.steps:
            for dependency in step.dependencies:
                if (
                    listed_index[dependency]
                    > listed_index[step.step_id]
                ):
                    issues.append(
                        PlanValidationIssue(
                            code=(
                                PlanValidationCode
                                .DEPENDENCY_ORDER_VIOLATION
                            ),
                            severity=(
                                PlanValidationSeverity.WARNING
                            ),
                            message=(
                                f"Step {step.step_id} appears "
                                f"before dependency {dependency} "
                                "in the plan step list."
                            ),
                            step_id=step.step_id,
                            related_step_ids=[
                                dependency
                            ],
                        )
                    )

                if (
                    execution_index[dependency]
                    >= execution_index[step.step_id]
                ):
                    raise RuntimeError(
                        "invalid topological order"
                    )

        return issues

    @staticmethod
    def _step_status_issues(
        plan: Plan,
    ) -> list[PlanValidationIssue]:
        """Validate each step against dependency states."""

        step_by_id = {
            step.step_id: step
            for step in plan.steps
        }
        issues: list[PlanValidationIssue] = []

        for step in plan.steps:
            dependencies = [
                step_by_id[dependency]
                for dependency in step.dependencies
            ]

            incomplete_dependencies = [
                dependency.step_id
                for dependency in dependencies
                if dependency.status
                not in {
                    PlanStepStatus.COMPLETED,
                    PlanStepStatus.SKIPPED,
                }
            ]

            failed_dependencies = [
                dependency.step_id
                for dependency in dependencies
                if dependency.status
                is PlanStepStatus.FAILED
            ]

            if (
                step.status is PlanStepStatus.READY
                and incomplete_dependencies
            ):
                issues.append(
                    PlanValidationIssue(
                        code=(
                            PlanValidationCode
                            .READY_WITH_INCOMPLETE_DEPENDENCY
                        ),
                        severity=(
                            PlanValidationSeverity.ERROR
                        ),
                        message=(
                            f"Step {step.step_id} is ready "
                            "but has incomplete dependencies."
                        ),
                        step_id=step.step_id,
                        related_step_ids=(
                            incomplete_dependencies
                        ),
                    )
                )

            if (
                step.status is PlanStepStatus.PENDING
                and dependencies
                and not incomplete_dependencies
            ):
                issues.append(
                    PlanValidationIssue(
                        code=(
                            PlanValidationCode
                            .PENDING_WITH_COMPLETED_DEPENDENCIES
                        ),
                        severity=(
                            PlanValidationSeverity.WARNING
                        ),
                        message=(
                            f"Step {step.step_id} is pending "
                            "although all dependencies are complete."
                        ),
                        step_id=step.step_id,
                        related_step_ids=[
                            dependency.step_id
                            for dependency in dependencies
                        ],
                    )
                )

            if (
                failed_dependencies
                and step.status
                in {
                    PlanStepStatus.READY,
                    PlanStepStatus.IN_PROGRESS,
                }
            ):
                issues.append(
                    PlanValidationIssue(
                        code=(
                            PlanValidationCode
                            .DEPENDS_ON_FAILED_STEP
                        ),
                        severity=(
                            PlanValidationSeverity.ERROR
                        ),
                        message=(
                            f"Step {step.step_id} depends "
                            "on a failed step."
                        ),
                        step_id=step.step_id,
                        related_step_ids=(
                            failed_dependencies
                        ),
                    )
                )

        return issues

    @staticmethod
    def _plan_status_issues(
        plan: Plan,
    ) -> list[PlanValidationIssue]:
        """Validate overall plan status against step states."""

        issues: list[PlanValidationIssue] = []
        active_statuses = {
            PlanStepStatus.READY,
            PlanStepStatus.IN_PROGRESS,
        }

        if (
            plan.status
            in {
                PlanStatus.COMPLETED,
                PlanStatus.FAILED,
                PlanStatus.CANCELLED,
            }
            and any(
                step.status in active_statuses
                for step in plan.steps
            )
        ):
            issues.append(
                PlanValidationIssue(
                    code=(
                        PlanValidationCode
                        .TERMINAL_PLAN_HAS_ACTIVE_STEPS
                    ),
                    severity=(
                        PlanValidationSeverity.ERROR
                    ),
                    message=(
                        "A terminal plan must not contain "
                        "ready or in-progress steps."
                    ),
                )
            )

        if (
            plan.status is PlanStatus.COMPLETED
            and any(
                step.status
                not in {
                    PlanStepStatus.COMPLETED,
                    PlanStepStatus.SKIPPED,
                }
                for step in plan.steps
            )
        ):
            issues.append(
                PlanValidationIssue(
                    code=(
                        PlanValidationCode
                        .COMPLETED_PLAN_HAS_INCOMPLETE_STEPS
                    ),
                    severity=(
                        PlanValidationSeverity.ERROR
                    ),
                    message=(
                        "A completed plan contains "
                        "incomplete steps."
                    ),
                )
            )

        if (
            plan.status is PlanStatus.FAILED
            and not any(
                step.status is PlanStepStatus.FAILED
                for step in plan.steps
            )
        ):
            issues.append(
                PlanValidationIssue(
                    code=(
                        PlanValidationCode
                        .FAILED_PLAN_HAS_NO_FAILED_STEP
                    ),
                    severity=(
                        PlanValidationSeverity.WARNING
                    ),
                    message=(
                        "The plan is failed but no step "
                        "is marked as failed."
                    ),
                )
            )

        return issues
