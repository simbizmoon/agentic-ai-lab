"""Full bounded scholarly evidence workflow with private persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_evidence_writer import (
    ScholarlyEvidenceArtifactPaths,
    ScholarlyEvidenceWriter,
)
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest
from app.schemas.scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflowResult,
)
from app.schemas.scholarly_provider import ScholarlySearchRequest


@dataclass(frozen=True)
class ScholarlyEvidenceFullWorkflowResult:
    """User request, provider request, evidence result, and persisted paths."""

    request: ScholarlyEvidenceRequest
    provider_request: ScholarlySearchRequest
    workflow_result: BoundedScholarlyEvidenceWorkflowResult
    artifact_paths: ScholarlyEvidenceArtifactPaths


class ScholarlyEvidenceFullWorkflow:
    """Compose bounded scholarly acquisition through artifact persistence."""

    def __init__(
        self,
        *,
        evidence_workflow: BoundedScholarlyEvidenceWorkflow,
        writer: ScholarlyEvidenceWriter | None = None,
    ) -> None:
        self._evidence_workflow = evidence_workflow
        self._writer = writer or ScholarlyEvidenceWriter()

    def execute(
        self,
        request: ScholarlyEvidenceRequest,
        *,
        request_id: str,
        task_id: str,
        output_dir: Path,
        execution_id: str,
    ) -> ScholarlyEvidenceFullWorkflowResult:
        """Run exactly one bounded provider workflow and persist its exact result."""

        if not isinstance(request, ScholarlyEvidenceRequest):
            raise TypeError("request must be a ScholarlyEvidenceRequest")
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir must be a Path")
        if not isinstance(task_id, str):
            raise TypeError("task_id must be a string")
        normalized_task_id = task_id.strip()
        if not normalized_task_id:
            raise ValueError("task_id must not be blank")

        provider_request = request.to_provider_request(request_id=request_id)
        workflow_result = self._evidence_workflow.run(
            provider_request,
            task_id=normalized_task_id,
        )
        if workflow_result.request != provider_request:
            raise RuntimeError("evidence workflow did not preserve provider request")
        if workflow_result.actual_provider_requests > request.maximum_provider_requests:
            raise RuntimeError("evidence workflow exceeded provider request budget")

        artifact_paths = self._writer.write(
            workflow_result,
            output_dir=output_dir,
            execution_id=execution_id,
        )
        return ScholarlyEvidenceFullWorkflowResult(
            request=request,
            provider_request=provider_request,
            workflow_result=workflow_result,
            artifact_paths=artifact_paths,
        )
