"""Stage 9 adapter for bounded scholarly metadata and abstract evidence."""

from __future__ import annotations

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
)
from app.schemas.scholarly_provider import (
    ScholarlySearchRequest,
    ScholarlySearchStatus,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequest,
)
from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain


class Stage9ScholarlyAcquisitionAdapter:
    """Use only a case question to obtain bounded whole-abstract evidence."""

    def __init__(self, *, workflow: BoundedScholarlyEvidenceWorkflow) -> None:
        if not isinstance(workflow, BoundedScholarlyEvidenceWorkflow):
            raise TypeError("workflow must be BoundedScholarlyEvidenceWorkflow")
        self._workflow = workflow

    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        if channel is not Stage9AcquisitionChannel.SCHOLARLY_PRIMARY:
            raise ValueError("scholarly adapter only accepts scholarly_primary")
        if request.domain not in {
            Stage9EvaluationDomain.ACADEMIC,
            Stage9EvaluationDomain.CROSS_SOURCE,
        }:
            raise ValueError("scholarly adapter requires an academic-capable domain")

        provider_request = ScholarlySearchRequest(
            request_id=request.request_id,
            query=request.question,
            maximum_results=min(request.budget.maximum_documents, 4),
            maximum_provider_requests=1,
            require_abstract=True,
            metadata={
                "stage9_case_id": request.case_id,
                "acquisition_channel": channel.value,
                "golden_evidence_supplied": "false",
            },
        )
        result = self._workflow.run(
            provider_request,
            task_id=f"{request.request_id}-scholarly",
        )
        provider_result = result.adaptation.document_adaptation.artifact.result
        status = self._status(
            provider_status=provider_result.status,
            evidence_count=len(result.adaptation.evidence_set.evidence),
        )
        failure_code = (
            provider_result.error.error_type
            if status is Stage9AcquisitionStatus.FAILED
            and provider_result.error is not None
            else None
        )
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=status,
            evidence_set=result.adaptation.evidence_set,
            provider_requests=result.actual_provider_requests,
            external_requests=result.actual_provider_requests,
            failure_code=failure_code,
        )

    @staticmethod
    def _status(
        *,
        provider_status: ScholarlySearchStatus,
        evidence_count: int,
    ) -> Stage9AcquisitionStatus:
        if provider_status is ScholarlySearchStatus.FAILED:
            return Stage9AcquisitionStatus.FAILED
        if provider_status is ScholarlySearchStatus.PARTIAL:
            return Stage9AcquisitionStatus.INCOMPLETE
        if evidence_count:
            return Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
        return Stage9AcquisitionStatus.NO_EVIDENCE
