"""Bounded scholarly metadata-to-evidence workflow."""

from __future__ import annotations

from app.research.bounded_scholarly_search_workflow import (
    BoundedScholarlySearchWorkflow,
)
from app.research.scholarly_artifact_evidence_runtime import (
    ScholarlyArtifactEvidenceRuntime,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflowResult,
)
from app.schemas.scholarly_provider import ScholarlySearchRequest


class BoundedScholarlyEvidenceWorkflow:
    """Compose one bounded provider search with exact abstract evidence."""

    def __init__(
        self,
        *,
        provider: ScholarlyMetadataProvider,
        artifact_runtime: ScholarlyArtifactEvidenceRuntime | None = None,
    ) -> None:
        self._search_workflow = BoundedScholarlySearchWorkflow(provider=provider)
        self._artifact_runtime = artifact_runtime or (
            ScholarlyArtifactEvidenceRuntime()
        )

    def run(
        self,
        request: ScholarlySearchRequest,
        *,
        task_id: str,
    ) -> BoundedScholarlyEvidenceWorkflowResult:
        """Execute the bounded search-to-evidence path."""

        if not task_id.strip():
            raise ValueError("task_id must not be blank")
        artifact = self._search_workflow.run(request)
        adaptation = self._artifact_runtime.build(
            artifact,
            task_id=task_id.strip(),
        )
        provider_result = artifact.result
        return BoundedScholarlyEvidenceWorkflowResult(
            request=request,
            task_id=task_id.strip(),
            adaptation=adaptation,
            maximum_provider_requests=request.maximum_provider_requests,
            actual_provider_requests=provider_result.usage.request_count,
            records_received=provider_result.usage.records_received,
            works_accepted=len(provider_result.works),
            records_rejected=provider_result.usage.records_rejected,
            abstract_documents_created=len(
                adaptation.document_adaptation.document_set.documents
            ),
            works_omitted_without_abstract=len(
                adaptation.document_adaptation.omitted_work_ids
            ),
            whole_abstract_evidence_created=len(adaptation.evidence_set.evidence),
            duplicate_identity_groups=len(artifact.duplicate_groups),
        )
