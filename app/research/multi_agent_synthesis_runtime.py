"""Runtime seams for deterministic multi-agent synthesis and report handoff."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.research.local_quality_review_executor import (
    InMemoryResearchReportRegistry,
)
from app.research.multi_agent_pipeline_executors import (
    MultiAgentResearchRuntimeContext,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesisExecutionResult,
    ResearchSynthesisExecutor,
    ResearchSynthesisExecutorError,
    ResearchSynthesizedReport,
    ResearchSynthesizedSection,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)


class RegisteredWorkspaceSynthesisExecutor(ResearchSynthesisExecutor):
    """Build a traceable report from the shared ResearchWorkspace."""

    def __init__(
        self,
        *,
        context: MultiAgentResearchRuntimeContext,
        report_registry: InMemoryResearchReportRegistry,
        report_reference_id_factory: Callable[[], str] | None = None,
        report_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._context = context
        self._report_registry = report_registry
        self._report_reference_id_factory = (
            report_reference_id_factory
            or (lambda: f"research-report-output-{uuid4()}")
        )
        self._report_id_factory = (
            report_id_factory
            or (lambda: f"research-report-{uuid4()}")
        )
        self._pending_reference_ids: list[str] = []

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        """Build and register one deterministic traceable report."""

        del assignment

        workspace = self._context.workspace
        claim_set = workspace.claim_set
        if claim_set is None or not claim_set.claims:
            raise ResearchSynthesisExecutorError(
                "shared workspace does not contain claims",
                code="NO_CLAIMS_FOR_SYNTHESIS",
                retryable=False,
            )

        report_id = self._new_identifier(
            self._report_id_factory,
            field_name="report_id",
        )
        reference_id = self._new_identifier(
            self._report_reference_id_factory,
            field_name="report_reference_id",
        )

        sections = [
            ResearchSynthesizedSection(
                section_id=f"{report_id}-section-{position:03d}",
                heading=f"Finding {position}",
                content=self._section_content(
                    claim=claim,
                    workspace=workspace,
                ),
                claim_ids=[claim.claim_id],
                order=position,
                metadata={
                    "synthesis": "deterministic-workspace",
                },
            )
            for position, claim in enumerate(
                claim_set.claims,
                start=1,
            )
        ]

        report = ResearchSynthesizedReport(
            report_id=report_id,
            title=f"Research Report: {workspace.request.question.strip()}",
            executive_summary=(
                f"{workspace.request.objective.strip()} "
                f"The report contains {len(claim_set.claims)} "
                "traceable claim(s) synthesized from the shared "
                "multi-agent research workspace."
            ),
            sections=sections,
            limitations=[
                (
                    "The report is deterministically synthesized from "
                    "the current workspace and does not make the local "
                    "quality reviewer authoritative."
                )
            ],
            follow_up_questions=[],
            metadata={
                "synthesis": "deterministic-workspace",
                "workspace_id": workspace.workspace_id,
            },
        )

        self._report_registry.register(
            reference_id=reference_id,
            report=report,
        )
        self._pending_reference_ids.append(reference_id)

        return ResearchSynthesisExecutionResult(
            requested_section_count=len(sections),
            report=report,
            tool_call_count=0,
            duration_ms=0,
            input_token_count=0,
            output_token_count=0,
            metadata={
                "synthesis": "deterministic-workspace",
                "report_reference_id": reference_id,
            },
        )

    def take_output_reference_id(self) -> str:
        """Return the reference registered by the latest synthesis execution."""

        if not self._pending_reference_ids:
            raise RuntimeError(
                "synthesis output reference requested before execution"
            )
        return self._pending_reference_ids.pop(0)

    @staticmethod
    def _section_content(*, claim: object, workspace: object) -> str:
        citations = claim.citations
        citation_lines = []
        for citation in citations:
            citation_lines.append(
                "Citation: "
                f"source_id={citation.source_id}; "
                f"document_id={citation.document_id}; "
                f"evidence_id={citation.evidence_id}; "
                f"excerpt={citation.excerpt}"
            )

        evidence_ids = list(
            claim.supporting_evidence_ids
        ) + list(
            claim.contradicting_evidence_ids
        )

        evidence_line = (
            "Evidence IDs: " + ", ".join(evidence_ids)
            if evidence_ids
            else "Evidence IDs: represented by claim citations."
        )

        source_lines = []
        document_set = workspace.document_set
        if document_set is not None:
            for document in document_set.documents:
                candidate = document.candidate
                source_lines.append(
                    "Source: "
                    f"title={candidate.title}; "
                    f"url={candidate.url}; "
                    f"type={candidate.source_type.value}"
                )

        pieces = [
            f"Claim: {claim.text}",
            evidence_line,
            *citation_lines,
            *source_lines,
        ]
        return "\n".join(pieces)

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        value = factory().strip()
        if not value:
            raise ResearchSynthesisExecutorError(
                f"{field_name} factory returned blank value",
                code="INVALID_SYNTHESIS_IDENTIFIER",
                retryable=False,
            )
        return value
