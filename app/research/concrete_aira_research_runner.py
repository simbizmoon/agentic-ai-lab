"""Concrete application runner for one single-agent research pipeline."""

from __future__ import annotations

from collections.abc import Callable

from app.application.research_execution import (
    ApplicationResearchExecutionOutput,
    ApplicationResearchExecutionRequest,
)
from app.research.application_research_request_adapter import (
    ApplicationResearchRequestAdapter,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)
from app.schemas.research_request import ResearchRequest

ResearchPipelineFactory = Callable[
    [ResearchRequest],
    SingleResearchAgentPipeline,
]


class ConcreteAiraResearchRunner:
    """Run a request-specific research pipeline and normalize its output."""

    def __init__(
        self,
        *,
        pipeline_factory: ResearchPipelineFactory,
        request_adapter: (
            ApplicationResearchRequestAdapter | None
        ) = None,
    ) -> None:
        self._pipeline_factory = pipeline_factory
        self._request_adapter = (
            request_adapter or ApplicationResearchRequestAdapter()
        )

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Execute one application research request."""

        research_request = self._request_adapter.adapt(request)
        pipeline = self._pipeline_factory(research_request)
        result = pipeline.run(
            research_request,
            workspace_id=request.workspace_id,
        )

        return self._output(result)

    @staticmethod
    def _output(
        result: SingleResearchPipelineResult,
    ) -> ApplicationResearchExecutionOutput:
        """Map a completed pipeline result to application output."""

        workspace = result.workspace
        documents = workspace.document_set
        evidence = workspace.evidence_set
        claims = workspace.claim_set
        progress = workspace.progress()

        citation_ids = [
            citation.citation_id
            for claim in claims.claims
            for citation in claim.citations
        ]

        return ApplicationResearchExecutionOutput(
            summary=result.report.executive_summary,
            result={
                "request_id": workspace.request.request_id,
                "workspace_id": workspace.workspace_id,
                "stage": workspace.stage.value,
                "report_title": result.report.title,
                "quality_score": result.quality.overall_score,
                "quality_level": result.quality.quality_level.value,
                "quality_passed": result.quality.passed,
                "task_count": progress.task_count,
                "query_count": progress.query_count,
                "candidate_count": progress.candidate_count,
                "document_count": progress.document_count,
                "successful_document_count": len(
                    documents.successful_documents()
                ),
                "failed_document_count": len(
                    documents.failed_documents()
                ),
                "evidence_count": len(evidence.evidence),
                "claim_count": len(claims.claims),
                "citation_count": len(citation_ids),
            },
            artifact_ids=[],
            citation_ids=citation_ids,
        )
