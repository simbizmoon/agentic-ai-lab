"""Deterministic orchestration of the multi-agent research workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.research.multi_agent_research_orchestrator_error import (
    MultiAgentResearchOrchestratorError,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoop,
    ReviewRevisionLoopResult,
    ReviewRevisionLoopStatus,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
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


class ResearchTaskAgent(Protocol):
    """Minimal contract required from a specialist agent."""

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return the specialist identity."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Execute one research assignment."""


class MultiAgentResearchStatus(StrEnum):
    """Terminal state of one multi-agent research execution."""

    COMPLETED = "completed"
    SEARCH_FAILED = "search_failed"
    SOURCE_READING_FAILED = "source_reading_failed"
    EVIDENCE_FAILED = "evidence_failed"
    CLAIM_FAILED = "claim_failed"
    SYNTHESIS_FAILED = "synthesis_failed"
    REVIEW_FAILED = "review_failed"
    REPORT_REJECTED = "report_rejected"
    REVISION_LIMIT_REACHED = "revision_limit_reached"


class MultiAgentResearchStage(StrEnum):
    """Named stage in the research pipeline."""

    SEARCH = "search"
    SOURCE_READING = "source_reading"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    CLAIM_CONSTRUCTION = "claim_construction"


class MultiAgentResearchStageResult(BaseModel):
    """One completed pre-synthesis research stage."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    stage: MultiAgentResearchStage
    assignment: ResearchAgentTaskAssignment
    result: ResearchAgentTaskResult


class MultiAgentResearchWorkflowResult(BaseModel):
    """Complete multi-agent research workflow result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    status: MultiAgentResearchStatus
    stages: list[MultiAgentResearchStageResult] = Field(
        default_factory=list
    )
    review_revision_result: (
        ReviewRevisionLoopResult | None
    ) = None
    final_result: ResearchAgentTaskResult
    summary: str

    @property
    def completed(self) -> bool:
        """Return whether the final report was approved."""

        return self.status is MultiAgentResearchStatus.COMPLETED


class MultiAgentResearchOrchestrator:
    """Run specialist agents in a deterministic research pipeline."""

    def __init__(
        self,
        *,
        search_agent: ResearchTaskAgent,
        source_reader_agent: ResearchTaskAgent,
        evidence_analyst_agent: ResearchTaskAgent,
        claim_analyst_agent: ResearchTaskAgent,
        review_revision_loop: ReviewRevisionLoop,
    ) -> None:
        self._search_agent = search_agent
        self._source_reader_agent = source_reader_agent
        self._evidence_analyst_agent = (
            evidence_analyst_agent
        )
        self._claim_analyst_agent = claim_analyst_agent
        self._review_revision_loop = (
            review_revision_loop
        )

    def run(
        self,
        *,
        search_assignment: ResearchAgentTaskAssignment,
        source_reader_template: ResearchAgentTaskAssignment,
        evidence_template: ResearchAgentTaskAssignment,
        claim_template: ResearchAgentTaskAssignment,
        synthesis_template: ResearchAgentTaskAssignment,
        review_template: ResearchAgentTaskAssignment,
    ) -> MultiAgentResearchWorkflowResult:
        """Run the complete multi-agent research workflow."""

        templates = [
            search_assignment,
            source_reader_template,
            evidence_template,
            claim_template,
            synthesis_template,
            review_template,
        ]
        self._validate_shared_context(templates)
        self._validate_agent_targets(
            search_assignment=search_assignment,
            source_reader_template=source_reader_template,
            evidence_template=evidence_template,
            claim_template=claim_template,
        )

        stages: list[MultiAgentResearchStageResult] = []

        search_result = self._search_agent.execute(
            search_assignment
        )
        stages.append(
            MultiAgentResearchStageResult(
                stage=MultiAgentResearchStage.SEARCH,
                assignment=search_assignment,
                result=search_result,
            )
        )

        if self._failed(search_result):
            return self._failed_workflow(
                status=MultiAgentResearchStatus.SEARCH_FAILED,
                stages=stages,
                final_result=search_result,
                summary=(
                    "The multi-agent workflow stopped "
                    "because source search failed."
                ),
            )

        source_reader_assignment = (
            self._assignment_from_output(
                template=source_reader_template,
                previous_result=search_result,
                input_name="search-results",
                reference_type=(
                    "research_source_candidate_set"
                ),
                parent_assignment_id=(
                    search_assignment.assignment_id
                ),
            )
        )
        source_reader_result = (
            self._source_reader_agent.execute(
                source_reader_assignment
            )
        )
        stages.append(
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage.SOURCE_READING
                ),
                assignment=source_reader_assignment,
                result=source_reader_result,
            )
        )

        if self._failed(source_reader_result):
            return self._failed_workflow(
                status=(
                    MultiAgentResearchStatus
                    .SOURCE_READING_FAILED
                ),
                stages=stages,
                final_result=source_reader_result,
                summary=(
                    "The multi-agent workflow stopped "
                    "because source reading failed."
                ),
            )

        evidence_assignment = self._assignment_from_output(
            template=evidence_template,
            previous_result=source_reader_result,
            input_name="source-documents",
            reference_type=(
                "research_source_document_set"
            ),
            parent_assignment_id=(
                source_reader_assignment.assignment_id
            ),
        )
        evidence_result = (
            self._evidence_analyst_agent.execute(
                evidence_assignment
            )
        )
        stages.append(
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .EVIDENCE_EXTRACTION
                ),
                assignment=evidence_assignment,
                result=evidence_result,
            )
        )

        if self._failed(evidence_result):
            return self._failed_workflow(
                status=MultiAgentResearchStatus.EVIDENCE_FAILED,
                stages=stages,
                final_result=evidence_result,
                summary=(
                    "The multi-agent workflow stopped "
                    "because evidence extraction failed."
                ),
            )

        claim_assignment = self._assignment_from_output(
            template=claim_template,
            previous_result=evidence_result,
            input_name="research-evidence",
            reference_type="research_evidence_set",
            parent_assignment_id=(
                evidence_assignment.assignment_id
            ),
        )
        claim_result = self._claim_analyst_agent.execute(
            claim_assignment
        )
        stages.append(
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .CLAIM_CONSTRUCTION
                ),
                assignment=claim_assignment,
                result=claim_result,
            )
        )

        if self._failed(claim_result):
            return self._failed_workflow(
                status=MultiAgentResearchStatus.CLAIM_FAILED,
                stages=stages,
                final_result=claim_result,
                summary=(
                    "The multi-agent workflow stopped "
                    "because claim construction failed."
                ),
            )

        synthesis_assignment = (
            self._assignment_from_output(
                template=synthesis_template,
                previous_result=claim_result,
                input_name="research-claims",
                reference_type="research_claim_set",
                parent_assignment_id=(
                    claim_assignment.assignment_id
                ),
            )
        )

        loop_result = self._review_revision_loop.run(
            initial_synthesis_assignment=(
                synthesis_assignment
            ),
            review_assignment_template=review_template,
        )

        status = self._workflow_status(loop_result)
        final_result = (
            loop_result.final_review_result
            or loop_result.final_synthesis_result
        )

        return MultiAgentResearchWorkflowResult(
            request_id=search_assignment.request_id,
            workspace_id=search_assignment.workspace_id,
            status=status,
            stages=stages,
            review_revision_result=loop_result,
            final_result=final_result,
            summary=self._workflow_summary(status),
        )

    def _validate_shared_context(
        self,
        assignments: list[ResearchAgentTaskAssignment],
    ) -> None:
        """Require one request and workspace across all templates."""

        request_ids = {
            assignment.request_id
            for assignment in assignments
        }
        workspace_ids = {
            assignment.workspace_id
            for assignment in assignments
        }

        if len(request_ids) != 1:
            raise MultiAgentResearchOrchestratorError(
                "all assignments must share request_id"
            )

        if len(workspace_ids) != 1:
            raise MultiAgentResearchOrchestratorError(
                "all assignments must share workspace_id"
            )

    def _validate_agent_targets(
        self,
        *,
        search_assignment: ResearchAgentTaskAssignment,
        source_reader_template: ResearchAgentTaskAssignment,
        evidence_template: ResearchAgentTaskAssignment,
        claim_template: ResearchAgentTaskAssignment,
    ) -> None:
        """Require templates to target configured agents."""

        pairs = [
            (
                search_assignment,
                self._search_agent,
                "search assignment",
            ),
            (
                source_reader_template,
                self._source_reader_agent,
                "source reader template",
            ),
            (
                evidence_template,
                self._evidence_analyst_agent,
                "evidence template",
            ),
            (
                claim_template,
                self._claim_analyst_agent,
                "claim template",
            ),
        ]

        for assignment, agent, label in pairs:
            if (
                assignment.assignee.agent_id
                .strip()
                .casefold()
                != agent.identity.agent_id
                .strip()
                .casefold()
            ):
                raise MultiAgentResearchOrchestratorError(
                    f"{label} must target its configured agent"
                )

    @staticmethod
    def _assignment_from_output(
        *,
        template: ResearchAgentTaskAssignment,
        previous_result: ResearchAgentTaskResult,
        input_name: str,
        reference_type: str,
        parent_assignment_id: str,
    ) -> ResearchAgentTaskAssignment:
        """Create the next assignment from a primary output."""

        output = previous_result.primary_output()

        if output is None:
            raise MultiAgentResearchOrchestratorError(
                "successful stage result must include "
                "a primary output"
            )

        artifact_input = ResearchAgentAssignmentInput(
            name=input_name,
            reference_type=reference_type,
            reference_id=output.reference_id,
        )

        return template.model_copy(
            update={
                "inputs": [artifact_input],
                "status": (
                    ResearchAgentAssignmentStatus.IN_PROGRESS
                ),
                "parent_assignment_id": (
                    parent_assignment_id
                ),
            }
        )

    @staticmethod
    def _failed(
        result: ResearchAgentTaskResult,
    ) -> bool:
        """Return whether a stage produced a failed result."""

        return (
            result.status
            is ResearchAgentResultStatus.FAILED
        )

    @staticmethod
    def _workflow_status(
        loop_result: ReviewRevisionLoopResult,
    ) -> MultiAgentResearchStatus:
        """Convert loop status to workflow status."""

        mapping = {
            ReviewRevisionLoopStatus.APPROVED: (
                MultiAgentResearchStatus.COMPLETED
            ),
            ReviewRevisionLoopStatus.REJECTED: (
                MultiAgentResearchStatus.REPORT_REJECTED
            ),
            ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED: (
                MultiAgentResearchStatus.REVISION_LIMIT_REACHED
            ),
            ReviewRevisionLoopStatus.SYNTHESIS_FAILED: (
                MultiAgentResearchStatus.SYNTHESIS_FAILED
            ),
            ReviewRevisionLoopStatus.REVIEW_FAILED: (
                MultiAgentResearchStatus.REVIEW_FAILED
            ),
        }

        return mapping[loop_result.status]

    @staticmethod
    def _workflow_summary(
        status: MultiAgentResearchStatus,
    ) -> str:
        """Return one deterministic workflow summary."""

        summaries = {
            MultiAgentResearchStatus.COMPLETED: (
                "The multi-agent research workflow completed "
                "with an approved report."
            ),
            MultiAgentResearchStatus.REPORT_REJECTED: (
                "The multi-agent research workflow completed "
                "with a rejected report."
            ),
            MultiAgentResearchStatus.REVISION_LIMIT_REACHED: (
                "The multi-agent research workflow reached "
                "the configured revision limit."
            ),
            MultiAgentResearchStatus.SYNTHESIS_FAILED: (
                "The multi-agent research workflow stopped "
                "because report synthesis failed."
            ),
            MultiAgentResearchStatus.REVIEW_FAILED: (
                "The multi-agent research workflow stopped "
                "because quality review failed."
            ),
        }

        return summaries[status]

    @staticmethod
    def _failed_workflow(
        *,
        status: MultiAgentResearchStatus,
        stages: list[MultiAgentResearchStageResult],
        final_result: ResearchAgentTaskResult,
        summary: str,
    ) -> MultiAgentResearchWorkflowResult:
        """Build a workflow result for a failed early stage."""

        assignment = stages[0].assignment

        return MultiAgentResearchWorkflowResult(
            request_id=assignment.request_id,
            workspace_id=assignment.workspace_id,
            status=status,
            stages=stages,
            final_result=final_result,
            summary=summary,
        )
