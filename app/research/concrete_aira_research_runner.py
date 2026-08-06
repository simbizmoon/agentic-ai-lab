"""Concrete application runner for one single-agent research pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from app.application.research_execution import (
    ApplicationResearchExecutionOutput,
    ApplicationResearchExecutionRequest,
)
from app.research.application_research_request_adapter import (
    ApplicationResearchRequestAdapter,
)
from app.research.research_result_writer import (
    ResearchResultPaths,
    ResearchResultWriter,
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
ArtifactExecutionIdFactory = Callable[
    [ApplicationResearchExecutionRequest],
    str,
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
        writer: ResearchResultWriter | None = None,
        output_dir: Path | None = None,
        artifact_execution_id_factory: (
            ArtifactExecutionIdFactory | None
        ) = None,
    ) -> None:
        if (writer is None) != (output_dir is None):
            raise ValueError(
                "writer and output_dir must be provided together"
            )

        self._pipeline_factory = pipeline_factory
        self._request_adapter = (
            request_adapter or ApplicationResearchRequestAdapter()
        )
        self._writer = writer
        self._output_dir = output_dir
        self._artifact_execution_id_factory = (
            artifact_execution_id_factory
            or self._default_artifact_execution_id
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
        paths = self._write_artifacts(
            request=request,
            result=result,
        )

        return self._output(
            result,
            paths=paths,
        )

    def _write_artifacts(
        self,
        *,
        request: ApplicationResearchExecutionRequest,
        result: SingleResearchPipelineResult,
    ) -> ResearchResultPaths | None:
        """Persist the completed result when a writer is configured."""

        if self._writer is None or self._output_dir is None:
            return None

        execution_id = self._artifact_execution_id_factory(
            request
        ).strip()

        if not execution_id:
            raise RuntimeError(
                "artifact execution ID factory returned blank value"
            )

        return self._writer.write(
            result,
            output_dir=self._output_dir,
            execution_id=execution_id,
        )

    @staticmethod
    def _output(
        result: SingleResearchPipelineResult,
        *,
        paths: ResearchResultPaths | None,
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
        artifact_ids: list[str] = []
        artifact_paths: dict[str, str] = {}

        if paths is not None:
            artifact_id = paths.execution_dir.name
            artifact_ids = [
                f"{artifact_id}:report",
                f"{artifact_id}:result",
            ]
            artifact_paths = {
                "execution_dir": str(paths.execution_dir),
                "report": str(paths.report_path),
                "result": str(paths.result_path),
            }

        return ApplicationResearchExecutionOutput(
            summary=result.report.executive_summary,
            result={
                "request_id": workspace.request.request_id,
                "workspace_id": workspace.workspace_id,
                "stage": workspace.stage.name.casefold(),
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
                "artifact_paths": artifact_paths,
            },
            artifact_ids=artifact_ids,
            citation_ids=citation_ids,
        )

    @staticmethod
    def _default_artifact_execution_id(
        request: ApplicationResearchExecutionRequest,
    ) -> str:
        """Return a unique artifact execution identifier."""

        return (
            f"{request.request_id}-attempt-"
            f"{request.attempt_number:03d}-{uuid4().hex}"
        )
