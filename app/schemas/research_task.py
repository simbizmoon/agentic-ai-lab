"""Schemas for research tasks and dependency graphs."""

from __future__ import annotations

from collections import deque
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResearchTaskPriority(StrEnum):
    """Priority assigned to a research task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResearchTaskStatus(StrEnum):
    """Lifecycle status of a research task."""

    PLANNED = "planned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ResearchTask(BaseModel):
    """One executable unit of research work."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    task_id: str
    request_id: str
    title: str
    question: str
    objective: str
    priority: ResearchTaskPriority = (
        ResearchTaskPriority.MEDIUM
    )
    status: ResearchTaskStatus = (
        ResearchTaskStatus.PLANNED
    )
    depends_on: list[str] = Field(
        default_factory=list
    )
    completion_criteria: list[str] = Field(
        default_factory=list,
        min_length=1,
    )
    requires_search: bool = True
    expected_output: str
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_task(self) -> Self:
        """Validate text, dependencies, and criteria."""

        required_text = {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "title": self.title,
            "question": self.question,
            "objective": self.objective,
            "expected_output": self.expected_output,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        normalized_dependencies = [
            dependency.strip().casefold()
            for dependency in self.depends_on
        ]

        if any(
            not dependency.strip()
            for dependency in self.depends_on
        ):
            raise ValueError(
                "depends_on must not contain blank values"
            )

        if len(set(normalized_dependencies)) != len(
            normalized_dependencies
        ):
            raise ValueError(
                "depends_on must not contain duplicates"
            )

        if self.task_id.strip().casefold() in (
            normalized_dependencies
        ):
            raise ValueError(
                "task must not depend on itself"
            )

        normalized_criteria: list[str] = []

        for criterion in self.completion_criteria:
            if not criterion.strip():
                raise ValueError(
                    "completion_criteria must not contain "
                    "blank values"
                )

            normalized_criteria.append(
                criterion.strip().casefold()
            )

        if len(set(normalized_criteria)) != len(
            normalized_criteria
        ):
            raise ValueError(
                "completion_criteria must not contain "
                "duplicates"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class ResearchTaskGraph(BaseModel):
    """Validated dependency graph for research tasks."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    tasks: list[ResearchTask] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        """Validate task identity and dependency integrity."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        task_ids = [
            task.task_id
            for task in self.tasks
        ]
        normalized_task_ids = [
            task_id.strip().casefold()
            for task_id in task_ids
        ]

        if len(set(normalized_task_ids)) != len(
            normalized_task_ids
        ):
            raise ValueError(
                "task IDs must be unique"
            )

        mismatched_request_ids = [
            task.task_id
            for task in self.tasks
            if task.request_id != self.request_id
        ]

        if mismatched_request_ids:
            raise ValueError(
                "all task request IDs must match "
                "the graph request_id"
            )

        task_id_lookup = {
            task.task_id.strip().casefold(): task.task_id
            for task in self.tasks
        }

        for task in self.tasks:
            for dependency in task.depends_on:
                dependency_key = (
                    dependency.strip().casefold()
                )

                if dependency_key not in task_id_lookup:
                    raise ValueError(
                        "all task dependencies must "
                        "reference existing tasks"
                    )

        self._validate_acyclic()

        return self

    def root_task_ids(self) -> list[str]:
        """Return task IDs with no dependencies."""

        return [
            task.task_id
            for task in self.tasks
            if not task.depends_on
        ]

    def topological_order(self) -> list[str]:
        """Return a deterministic dependency-safe order."""

        task_by_id = {
            task.task_id: task
            for task in self.tasks
        }
        original_position = {
            task.task_id: position
            for position, task in enumerate(self.tasks)
        }

        dependency_count = {
            task.task_id: len(task.depends_on)
            for task in self.tasks
        }
        dependents: dict[str, list[str]] = {
            task.task_id: []
            for task in self.tasks
        }

        normalized_to_actual = {
            task.task_id.strip().casefold(): task.task_id
            for task in self.tasks
        }

        for task in self.tasks:
            for dependency in task.depends_on:
                actual_dependency = normalized_to_actual[
                    dependency.strip().casefold()
                ]
                dependents[actual_dependency].append(
                    task.task_id
                )

        ready = deque(
            sorted(
                (
                    task_id
                    for task_id, count
                    in dependency_count.items()
                    if count == 0
                ),
                key=original_position.__getitem__,
            )
        )
        ordered: list[str] = []

        while ready:
            task_id = ready.popleft()
            ordered.append(task_id)

            newly_ready: list[str] = []

            for dependent_id in dependents[task_id]:
                dependency_count[dependent_id] -= 1

                if dependency_count[dependent_id] == 0:
                    newly_ready.append(dependent_id)

            for dependent_id in sorted(
                newly_ready,
                key=original_position.__getitem__,
            ):
                ready.append(dependent_id)

        if len(ordered) != len(task_by_id):
            raise ValueError(
                "research task graph must not contain cycles"
            )

        return ordered

    def _validate_acyclic(self) -> None:
        """Reject cyclic task dependencies."""

        try:
            self.topological_order()
        except ValueError as error:
            raise ValueError(
                "research task graph must not contain cycles"
            ) from error
