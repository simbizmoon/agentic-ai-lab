"""Deterministic validation of structured planner output."""

from __future__ import annotations

from collections import deque

from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationCode,
    PlannerOutputValidationIssue,
    PlannerOutputValidationResult,
)


class PlannerOutputValidator:
    """Validate planner output against one planning request."""

    def validate(
        self,
        *,
        request: PlanCreationRequest,
        output: PlanDraftOutput,
    ) -> PlannerOutputValidationResult:
        """Return deterministic planner-output validation."""

        issues: list[PlannerOutputValidationIssue] = []

        if len(output.steps) > request.maximum_steps:
            issues.append(
                PlannerOutputValidationIssue(
                    code=(
                        PlannerOutputValidationCode
                        .TOO_MANY_STEPS
                    ),
                    message=(
                        "Planner output exceeds maximum_steps."
                    ),
                )
            )

        available_tools = set(
            request.available_tools
        )

        for step in output.steps:
            if (
                request.require_tool_for_each_step
                and step.tool_name is None
            ):
                issues.append(
                    PlannerOutputValidationIssue(
                        code=(
                            PlannerOutputValidationCode
                            .TOOL_REQUIRED
                        ),
                        message=(
                            f"Step {step.step_id} requires "
                            "a tool."
                        ),
                        step_id=step.step_id,
                    )
                )

            if (
                step.tool_name is not None
                and step.tool_name
                not in available_tools
            ):
                issues.append(
                    PlannerOutputValidationIssue(
                        code=(
                            PlannerOutputValidationCode
                            .TOOL_NOT_AVAILABLE
                        ),
                        message=(
                            f"Step {step.step_id} uses "
                            f"unavailable tool "
                            f"{step.tool_name}."
                        ),
                        step_id=step.step_id,
                    )
                )

        execution_order = self._topological_order(
            output
        )

        if execution_order is None:
            issues.append(
                PlannerOutputValidationIssue(
                    code=(
                        PlannerOutputValidationCode
                        .CIRCULAR_DEPENDENCY
                    ),
                    message=(
                        "Planner output contains a circular "
                        "dependency."
                    ),
                    related_step_ids=[
                        step.step_id
                        for step in output.steps
                    ],
                )
            )
            execution_order = []

        if (
            not request.allow_parallel_steps
            and self._has_parallel_steps(output)
        ):
            issues.append(
                PlannerOutputValidationIssue(
                    code=(
                        PlannerOutputValidationCode
                        .PARALLEL_STEPS_NOT_ALLOWED
                    ),
                    message=(
                        "Planner output contains parallel "
                        "steps although parallel execution "
                        "is disabled."
                    ),
                )
            )

        return PlannerOutputValidationResult(
            valid=not issues,
            issues=issues,
            execution_order=execution_order,
        )

    @staticmethod
    def _topological_order(
        output: PlanDraftOutput,
    ) -> list[str] | None:
        """Return dependency order or None for a cycle."""

        step_ids = [
            step.step_id
            for step in output.steps
        ]
        original_index = {
            step_id: index
            for index, step_id in enumerate(step_ids)
        }

        indegree = {
            step.step_id: len(step.dependencies)
            for step in output.steps
        }
        dependents = {
            step_id: []
            for step_id in step_ids
        }

        for step in output.steps:
            for dependency in step.dependencies:
                dependents[dependency].append(
                    step.step_id
                )

        for dependent_ids in dependents.values():
            dependent_ids.sort(
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
    def _has_parallel_steps(
        output: PlanDraftOutput,
    ) -> bool:
        """Return whether multiple steps can run together."""

        completed: set[str] = set()

        while len(completed) < len(output.steps):
            ready = [
                step
                for step in output.steps
                if step.step_id not in completed
                and set(step.dependencies).issubset(
                    completed
                )
            ]

            if len(ready) > 1:
                return True

            if not ready:
                return False

            completed.add(ready[0].step_id)

        return False
