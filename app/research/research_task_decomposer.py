"""Deterministic decomposition of research requests."""

from __future__ import annotations

from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.research.research_task_decomposition_error import (
    ResearchTaskDecompositionError,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
    ResearchTaskPriority,
    ResearchTaskStatus,
)
from app.schemas.research_task_decomposition import (
    ResearchTaskDecompositionResult,
)


class ResearchTaskDecomposer:
    """Convert a validated request into a research task graph."""

    def __init__(
        self,
        *,
        validator: ResearchRequestValidator | None = None,
    ) -> None:
        self._validator = (
            validator or ResearchRequestValidator()
        )

    @property
    def validator(self) -> ResearchRequestValidator:
        """Return the configured request validator."""

        return self._validator

    def decompose(
        self,
        request: ResearchRequest,
    ) -> ResearchTaskDecompositionResult:
        """Create a deterministic research task graph."""

        validation = self.validator.validate(request)

        if not validation.valid:
            raise ResearchTaskDecompositionError(
                validation
            )

        tasks = self._build_tasks(request)

        return ResearchTaskDecompositionResult(
            request=request,
            validation=validation,
            task_graph=ResearchTaskGraph(
                request_id=request.request_id,
                tasks=tasks,
            ),
        )

    def _build_tasks(
        self,
        request: ResearchRequest,
    ) -> list[ResearchTask]:
        """Build topic tasks and an optional synthesis task."""

        if not request.include_topics:
            return [
                self._build_general_task(
                    request=request
                )
            ]

        topic_tasks = [
            self._build_topic_task(
                request=request,
                topic=topic,
                position=position,
            )
            for position, topic in enumerate(
                request.include_topics,
                start=1,
            )
        ]

        if len(topic_tasks) == 1:
            return topic_tasks

        synthesis_position = len(topic_tasks) + 1

        return [
            *topic_tasks,
            self._build_synthesis_task(
                request=request,
                position=synthesis_position,
                dependencies=[
                    task.task_id
                    for task in topic_tasks
                ],
            ),
        ]

    def _build_general_task(
        self,
        *,
        request: ResearchRequest,
    ) -> ResearchTask:
        """Build one task for an unscoped research request."""

        return ResearchTask(
            task_id=self._task_id(
                request_id=request.request_id,
                position=1,
            ),
            request_id=request.request_id,
            title="Investigate the research question",
            question=request.question,
            objective=request.objective,
            priority=ResearchTaskPriority.HIGH,
            status=ResearchTaskStatus.PLANNED,
            depends_on=[],
            completion_criteria=[
                (
                    "Identify findings that directly answer "
                    "the research question"
                ),
                (
                    "Support material findings with "
                    "traceable sources"
                ),
            ],
            requires_search=True,
            expected_output=(
                "A structured collection of findings, "
                "evidence, and source references."
            ),
            metadata={
                "task_type": "general_research",
            },
        )

    def _build_topic_task(
        self,
        *,
        request: ResearchRequest,
        topic: str,
        position: int,
    ) -> ResearchTask:
        """Build one independent task for an included topic."""

        return ResearchTask(
            task_id=self._task_id(
                request_id=request.request_id,
                position=position,
            ),
            request_id=request.request_id,
            title=f"Investigate {topic.strip()}",
            question=(
                f"How does {topic.strip()} relate to the "
                f"research question: {request.question}"
            ),
            objective=(
                f"Produce verified findings about "
                f"{topic.strip()} that contribute to: "
                f"{request.objective}"
            ),
            priority=ResearchTaskPriority.HIGH,
            status=ResearchTaskStatus.PLANNED,
            depends_on=[],
            completion_criteria=[
                (
                    f"Explain the relevance of "
                    f"{topic.strip()} to the research question"
                ),
                (
                    f"Collect traceable evidence for "
                    f"{topic.strip()}"
                ),
            ],
            requires_search=True,
            expected_output=(
                f"Structured findings and evidence about "
                f"{topic.strip()}."
            ),
            metadata={
                "task_type": "topic_research",
                "topic": topic.strip(),
            },
        )

    def _build_synthesis_task(
        self,
        *,
        request: ResearchRequest,
        position: int,
        dependencies: list[str],
    ) -> ResearchTask:
        """Build a final task combining topic findings."""

        return ResearchTask(
            task_id=self._task_id(
                request_id=request.request_id,
                position=position,
            ),
            request_id=request.request_id,
            title="Synthesize research findings",
            question=request.question,
            objective=(
                "Combine the completed topic findings into "
                f"a coherent answer that satisfies: "
                f"{request.objective}"
            ),
            priority=ResearchTaskPriority.CRITICAL,
            status=ResearchTaskStatus.PLANNED,
            depends_on=dependencies,
            completion_criteria=[
                (
                    "Address the original research question "
                    "directly"
                ),
                (
                    "Reconcile relevant agreements and "
                    "conflicts across topic findings"
                ),
                (
                    "Preserve traceability to supporting "
                    "evidence and sources"
                ),
            ],
            requires_search=False,
            expected_output=(
                "An integrated research synthesis with "
                "traceable evidence."
            ),
            metadata={
                "task_type": "synthesis",
            },
        )

    @staticmethod
    def _task_id(
        *,
        request_id: str,
        position: int,
    ) -> str:
        """Return one deterministic task identifier."""

        return (
            f"{request_id.strip()}-task-"
            f"{position:03d}"
        )
