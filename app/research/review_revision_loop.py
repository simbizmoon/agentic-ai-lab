"""Deterministic quality-review and report-revision loop."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.research.quality_reviewer_agent import (
    QualityReviewerAgent,
)
from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
)
from app.research.review_revision_loop_error import (
    ReviewRevisionLoopError,
)
from app.research.synthesis_specialist_agent import (
    SynthesisSpecialistAgent,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_result import (
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)


class ReviewRevisionLoopStatus(StrEnum):
    """Terminal state of a report review and revision loop."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_LIMIT_REACHED = "revision_limit_reached"
    SYNTHESIS_FAILED = "synthesis_failed"
    REVIEW_FAILED = "review_failed"


class ReviewRevisionRound(BaseModel):
    """One synthesis and quality-review round."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    round_number: int = Field(ge=1)
    synthesis_assignment: ResearchAgentTaskAssignment
    synthesis_result: ResearchAgentTaskResult
    review_assignment: ResearchAgentTaskAssignment | None = None
    review_result: ResearchAgentTaskResult | None = None


class ReviewRevisionLoopResult(BaseModel):
    """Complete deterministic review and revision history."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    loop_id: str
    status: ReviewRevisionLoopStatus
    rounds: list[ReviewRevisionRound] = Field(min_length=1)
    maximum_revision_rounds: int = Field(ge=0)
    revision_rounds_used: int = Field(ge=0)
    final_synthesis_result: ResearchAgentTaskResult
    final_review_result: ResearchAgentTaskResult | None = None
    summary: str

    @property
    def approved(self) -> bool:
        """Return whether the final report was approved."""

        return self.status is ReviewRevisionLoopStatus.APPROVED

    @property
    def exhausted(self) -> bool:
        """Return whether the configured revision limit was reached."""

        return (
            self.status
            is ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED
        )


class ReviewRevisionLoop:
    """Coordinate synthesis, quality review, and revisions."""

    def __init__(
        self,
        *,
        synthesis_agent: SynthesisSpecialistAgent,
        quality_reviewer: QualityReviewerAgent,
        maximum_revision_rounds: int = 2,
        loop_id_factory: Callable[[], str] | None = None,
        synthesis_assignment_id_factory: (
            Callable[[int], str] | None
        ) = None,
        review_assignment_id_factory: (
            Callable[[int], str] | None
        ) = None,
    ) -> None:
        if maximum_revision_rounds < 0:
            raise ValueError(
                "maximum_revision_rounds must be nonnegative"
            )

        self._synthesis_agent = synthesis_agent
        self._quality_reviewer = quality_reviewer
        self._maximum_revision_rounds = (
            maximum_revision_rounds
        )
        self._loop_id_factory = (
            loop_id_factory
            or (lambda: f"review-loop-{uuid4()}")
        )
        self._synthesis_assignment_id_factory = (
            synthesis_assignment_id_factory
            or (
                lambda round_number: (
                    "synthesis-revision-"
                    f"{round_number}-{uuid4()}"
                )
            )
        )
        self._review_assignment_id_factory = (
            review_assignment_id_factory
            or (
                lambda round_number: (
                    f"quality-review-{round_number}-{uuid4()}"
                )
            )
        )

    def run(
        self,
        *,
        initial_synthesis_assignment: (
            ResearchAgentTaskAssignment
        ),
        review_assignment_template: (
            ResearchAgentTaskAssignment
        ),
    ) -> ReviewRevisionLoopResult:
        """Run synthesis and review until a terminal condition."""

        self._validate_templates(
            initial_synthesis_assignment=(
                initial_synthesis_assignment
            ),
            review_assignment_template=(
                review_assignment_template
            ),
        )

        loop_id = self._new_identifier(
            self._loop_id_factory,
            field_name="loop_id",
        )
        rounds: list[ReviewRevisionRound] = []
        synthesis_assignment = (
            initial_synthesis_assignment
        )
        revision_rounds_used = 0

        while True:
            round_number = len(rounds) + 1
            synthesis_result = (
                self._synthesis_agent.execute(
                    synthesis_assignment
                )
            )

            if (
                synthesis_result.status
                is ResearchAgentResultStatus.FAILED
            ):
                rounds.append(
                    ReviewRevisionRound(
                        round_number=round_number,
                        synthesis_assignment=(
                            synthesis_assignment
                        ),
                        synthesis_result=synthesis_result,
                    )
                )

                return ReviewRevisionLoopResult(
                    loop_id=loop_id,
                    status=(
                        ReviewRevisionLoopStatus
                        .SYNTHESIS_FAILED
                    ),
                    rounds=rounds,
                    maximum_revision_rounds=(
                        self._maximum_revision_rounds
                    ),
                    revision_rounds_used=(
                        revision_rounds_used
                    ),
                    final_synthesis_result=(
                        synthesis_result
                    ),
                    summary=(
                        "The review and revision loop "
                        "stopped because synthesis failed."
                    ),
                )

            report_reference_id = (
                self._primary_reference_id(
                    synthesis_result,
                    artifact_name="synthesis report",
                )
            )

            review_assignment = (
                self._build_review_assignment(
                    template=review_assignment_template,
                    round_number=round_number,
                    report_reference_id=(
                        report_reference_id
                    ),
                    parent_assignment_id=(
                        synthesis_assignment.assignment_id
                    ),
                )
            )
            review_result = (
                self._quality_reviewer.execute(
                    review_assignment
                )
            )

            rounds.append(
                ReviewRevisionRound(
                    round_number=round_number,
                    synthesis_assignment=(
                        synthesis_assignment
                    ),
                    synthesis_result=synthesis_result,
                    review_assignment=review_assignment,
                    review_result=review_result,
                )
            )

            if (
                review_result.status
                is ResearchAgentResultStatus.FAILED
            ):
                return ReviewRevisionLoopResult(
                    loop_id=loop_id,
                    status=(
                        ReviewRevisionLoopStatus
                        .REVIEW_FAILED
                    ),
                    rounds=rounds,
                    maximum_revision_rounds=(
                        self._maximum_revision_rounds
                    ),
                    revision_rounds_used=(
                        revision_rounds_used
                    ),
                    final_synthesis_result=(
                        synthesis_result
                    ),
                    final_review_result=review_result,
                    summary=(
                        "The review and revision loop "
                        "stopped because quality review failed."
                    ),
                )

            decision = self._review_decision(
                review_result
            )

            if decision is ResearchQualityDecision.APPROVED:
                return ReviewRevisionLoopResult(
                    loop_id=loop_id,
                    status=(
                        ReviewRevisionLoopStatus.APPROVED
                    ),
                    rounds=rounds,
                    maximum_revision_rounds=(
                        self._maximum_revision_rounds
                    ),
                    revision_rounds_used=(
                        revision_rounds_used
                    ),
                    final_synthesis_result=(
                        synthesis_result
                    ),
                    final_review_result=review_result,
                    summary=(
                        "The research report was approved "
                        "by the quality reviewer."
                    ),
                )

            if decision is ResearchQualityDecision.REJECTED:
                return ReviewRevisionLoopResult(
                    loop_id=loop_id,
                    status=(
                        ReviewRevisionLoopStatus.REJECTED
                    ),
                    rounds=rounds,
                    maximum_revision_rounds=(
                        self._maximum_revision_rounds
                    ),
                    revision_rounds_used=(
                        revision_rounds_used
                    ),
                    final_synthesis_result=(
                        synthesis_result
                    ),
                    final_review_result=review_result,
                    summary=(
                        "The research report was rejected "
                        "by the quality reviewer."
                    ),
                )

            if (
                revision_rounds_used
                >= self._maximum_revision_rounds
            ):
                return ReviewRevisionLoopResult(
                    loop_id=loop_id,
                    status=(
                        ReviewRevisionLoopStatus
                        .REVISION_LIMIT_REACHED
                    ),
                    rounds=rounds,
                    maximum_revision_rounds=(
                        self._maximum_revision_rounds
                    ),
                    revision_rounds_used=(
                        revision_rounds_used
                    ),
                    final_synthesis_result=(
                        synthesis_result
                    ),
                    final_review_result=review_result,
                    summary=(
                        "The report still required revision "
                        "after the configured revision limit."
                    ),
                )

            review_reference_id = (
                self._primary_reference_id(
                    review_result,
                    artifact_name="quality review",
                )
            )
            revision_rounds_used += 1
            synthesis_assignment = (
                self._build_revision_assignment(
                    previous_assignment=(
                        synthesis_assignment
                    ),
                    revision_round_number=(
                        revision_rounds_used
                    ),
                    report_reference_id=(
                        report_reference_id
                    ),
                    review_reference_id=(
                        review_reference_id
                    ),
                    review_result=review_result,
                )
            )

    def _validate_templates(
        self,
        *,
        initial_synthesis_assignment: (
            ResearchAgentTaskAssignment
        ),
        review_assignment_template: (
            ResearchAgentTaskAssignment
        ),
    ) -> None:
        """Validate agent and assignment-template alignment."""

        if (
            initial_synthesis_assignment.assignee.agent_id
            .strip()
            .casefold()
            != self._synthesis_agent.identity.agent_id
            .strip()
            .casefold()
        ):
            raise ReviewRevisionLoopError(
                "initial synthesis assignment must target "
                "the configured synthesis agent"
            )

        if (
            review_assignment_template.assignee.agent_id
            .strip()
            .casefold()
            != self._quality_reviewer.identity.agent_id
            .strip()
            .casefold()
        ):
            raise ReviewRevisionLoopError(
                "review assignment template must target "
                "the configured quality reviewer"
            )

        if (
            initial_synthesis_assignment.request_id
            != review_assignment_template.request_id
        ):
            raise ReviewRevisionLoopError(
                "synthesis and review assignments must share "
                "request_id"
            )

        if (
            initial_synthesis_assignment.workspace_id
            != review_assignment_template.workspace_id
        ):
            raise ReviewRevisionLoopError(
                "synthesis and review assignments must share "
                "workspace_id"
            )

    def _build_review_assignment(
        self,
        *,
        template: ResearchAgentTaskAssignment,
        round_number: int,
        report_reference_id: str,
        parent_assignment_id: str,
    ) -> ResearchAgentTaskAssignment:
        """Build one quality review assignment."""

        assignment_id = self._new_round_identifier(
            self._review_assignment_id_factory,
            round_number=round_number,
            field_name="review_assignment_id",
        )
        report_input = ResearchAgentAssignmentInput(
            name=f"report-round-{round_number}",
            reference_type="research_report",
            reference_id=report_reference_id,
        )

        return template.model_copy(
            update={
                "assignment_id": assignment_id,
                "inputs": [report_input],
                "status": (
                    ResearchAgentAssignmentStatus.IN_PROGRESS
                ),
                "attempt_number": round_number,
                "parent_assignment_id": (
                    parent_assignment_id
                ),
            }
        )

    def _build_revision_assignment(
        self,
        *,
        previous_assignment: ResearchAgentTaskAssignment,
        revision_round_number: int,
        report_reference_id: str,
        review_reference_id: str,
        review_result: ResearchAgentTaskResult,
    ) -> ResearchAgentTaskAssignment:
        """Build one synthesis revision assignment."""

        assignment_id = self._new_round_identifier(
            self._synthesis_assignment_id_factory,
            round_number=revision_round_number,
            field_name="synthesis_assignment_id",
        )
        report_input = ResearchAgentAssignmentInput(
            name=(
                f"previous-report-{revision_round_number}"
            ),
            reference_type="research_report",
            reference_id=report_reference_id,
        )
        review_input = ResearchAgentAssignmentInput(
            name=(
                f"quality-review-{revision_round_number}"
            ),
            reference_type="research_quality_review",
            reference_id=review_reference_id,
        )

        revision_instruction = (
            "Revise the previous report according to "
            "the attached quality review."
        )
        revision_instructions = self._merge_text_values(
            previous_assignment.instructions,
            [revision_instruction],
        )

        return previous_assignment.model_copy(
            update={
                "assignment_id": assignment_id,
                "inputs": self._merge_inputs(
                    previous_assignment.inputs,
                    [report_input, review_input],
                ),
                "instructions": revision_instructions,
                "status": (
                    ResearchAgentAssignmentStatus.IN_PROGRESS
                ),
                "attempt_number": (
                    previous_assignment.attempt_number + 1
                ),
                "maximum_attempts": max(
                    previous_assignment.maximum_attempts,
                    previous_assignment.attempt_number + 1,
                ),
                "parent_assignment_id": (
                    previous_assignment.assignment_id
                ),
                "metadata": {
                    **previous_assignment.metadata,
                    "revision_round": str(
                        revision_round_number
                    ),
                    "quality_decision": str(
                        review_result.payload.get(
                            "decision",
                            "revision_required",
                        )
                    ),
                },
            }
        )

    @staticmethod
    def _merge_text_values(
        existing: list[str],
        additions: list[str],
    ) -> list[str]:
        """Merge text values without case-insensitive duplicates."""

        merged = list(existing)
        normalized = {
            value.strip().casefold()
            for value in existing
        }

        for value in additions:
            key = value.strip().casefold()

            if key not in normalized:
                merged.append(value)
                normalized.add(key)

        return merged

    @staticmethod
    def _merge_inputs(
        existing: list[ResearchAgentAssignmentInput],
        additions: list[ResearchAgentAssignmentInput],
    ) -> list[ResearchAgentAssignmentInput]:
        """Merge assignment inputs without duplicate references."""

        merged = list(existing)
        references = {
            (
                item.reference_type.strip().casefold(),
                item.reference_id.strip().casefold(),
            )
            for item in existing
        }

        for item in additions:
            key = (
                item.reference_type.strip().casefold(),
                item.reference_id.strip().casefold(),
            )

            if key not in references:
                merged.append(item)
                references.add(key)

        return merged

    @staticmethod
    def _review_decision(
        review_result: ResearchAgentTaskResult,
    ) -> ResearchQualityDecision:
        """Read and validate the reviewer decision payload."""

        value = review_result.payload.get("decision")

        if not isinstance(value, str):
            raise ReviewRevisionLoopError(
                "quality review result must include "
                "a string decision"
            )

        try:
            return ResearchQualityDecision(value)
        except ValueError as exc:
            raise ReviewRevisionLoopError(
                "quality review result contains "
                f"unsupported decision: {value}"
            ) from exc

    @staticmethod
    def _primary_reference_id(
        result: ResearchAgentTaskResult,
        *,
        artifact_name: str,
    ) -> str:
        """Return the primary output reference from an agent result."""

        output = result.primary_output()

        if output is None:
            raise ReviewRevisionLoopError(
                f"{artifact_name} result must include "
                "a primary output"
            )

        return output.reference_id

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate one nonblank identifier."""

        value = factory()

        if not value.strip():
            raise ReviewRevisionLoopError(
                f"{field_name} factory returned blank value"
            )

        return value

    @staticmethod
    def _new_round_identifier(
        factory: Callable[[int], str],
        *,
        round_number: int,
        field_name: str,
    ) -> str:
        """Generate one nonblank round-specific identifier."""

        value = factory(round_number)

        if not value.strip():
            raise ReviewRevisionLoopError(
                f"{field_name} factory returned blank value"
            )

        return value
