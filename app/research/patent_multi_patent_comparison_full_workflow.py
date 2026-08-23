"""Full explicit-input patent comparison workflow composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.research.patent_claim_decomposition_grounding_validator import (
    PatentClaimDecompositionGroundingValidator,
)
from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntimeResult,
)
from app.research.patent_claims_runtime import PatentClaimsRuntimeResult
from app.research.patent_multi_patent_comparison_acquisition import (
    PatentMultiPatentComparisonAcquisition,
    PatentMultiPatentComparisonAcquisitionResult,
)
from app.research.patent_multi_patent_comparison_workflow import (
    PatentMultiPatentComparisonWorkflow,
    PatentMultiPatentComparisonWorkflowResult,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimsDocumentDecomposition,
    PatentClaimSetDecomposition,
)
from app.schemas.patent_claims import PatentClaim
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


class SelectedClaimDecompositionResultProtocol(Protocol):
    """Minimal result returned by one injected claim decomposer."""

    decomposition: PatentClaimDecomposition


class SelectedClaimDecomposerProtocol(Protocol):
    """Decompose exactly one already selected patent claim."""

    def decompose(
        self,
        claim: PatentClaim,
    ) -> SelectedClaimDecompositionResultProtocol: ...


class PatentMultiPatentSelectedClaimDecomposition:
    """Decompose only the claim explicitly selected during acquisition."""

    def __init__(
        self,
        *,
        claim_decomposer: SelectedClaimDecomposerProtocol,
        grounding_validator: PatentClaimDecompositionGroundingValidator | None = None,
    ) -> None:
        self._claim_decomposer = claim_decomposer
        self._grounding_validator = (
            grounding_validator or PatentClaimDecompositionGroundingValidator()
        )

    def decompose(
        self,
        acquisition: PatentMultiPatentComparisonAcquisitionResult,
    ) -> PatentClaimDecompositionRuntimeResult:
        claim = acquisition.selected_target_claim
        generated = self._claim_decomposer.decompose(claim)
        decomposition = self._grounding_validator.validate(
            claim=claim,
            decomposition=generated.decomposition,
        )
        if len(decomposition.elements) > acquisition.request.maximum_claim_elements:
            raise RuntimeError(
                "selected claim decomposition exceeds maximum_claim_elements"
            )

        document = acquisition.target_claims_document
        return PatentClaimDecompositionRuntimeResult(
            claims_result=PatentClaimsRuntimeResult(
                execution=acquisition.comparison_execution,
                claim_documents=(document,),
            ),
            decomposition_documents=(
                PatentClaimsDocumentDecomposition(
                    publication_number=document.publication_number,
                    publication_docdb=document.publication_docdb,
                    source_endpoint=document.source_endpoint,
                    claim_sets=(
                        PatentClaimSetDecomposition(
                            language=acquisition.request.claim_language,
                            claims=(decomposition,),
                        ),
                    ),
                ),
            ),
        )


@dataclass(frozen=True)
class PatentMultiPatentFullWorkflowResult:
    """Acquisition, selected decomposition, and downstream persisted result."""

    request: PatentMultiPatentComparisonRequest
    acquisition: PatentMultiPatentComparisonAcquisitionResult
    decomposition_result: PatentClaimDecompositionRuntimeResult
    workflow_result: PatentMultiPatentComparisonWorkflowResult


class PatentMultiPatentComparisonFullWorkflow:
    """Compose explicit acquisition through comparison artifact persistence."""

    def __init__(
        self,
        *,
        acquisition: PatentMultiPatentComparisonAcquisition,
        selected_decomposition: PatentMultiPatentSelectedClaimDecomposition,
        downstream_workflow: PatentMultiPatentComparisonWorkflow,
    ) -> None:
        self._acquisition = acquisition
        self._selected_decomposition = selected_decomposition
        self._downstream_workflow = downstream_workflow

    def execute(
        self,
        request: PatentMultiPatentComparisonRequest,
        *,
        request_id: str,
        output_dir: Path,
        execution_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentMultiPatentFullWorkflowResult:
        if not isinstance(request, PatentMultiPatentComparisonRequest):
            raise TypeError("request must be a PatentMultiPatentComparisonRequest")
        acquisition = self._acquisition.acquire(
            request,
            request_id=request_id,
            task_id=task_id,
        )
        if acquisition.request is not request:
            raise RuntimeError("acquisition did not preserve comparison request")

        decomposition_result = self._selected_decomposition.decompose(acquisition)
        workflow_result = self._downstream_workflow.execute(
            request,
            decomposition_result=decomposition_result,
            evidence_result=acquisition.evidence_result,
            output_dir=output_dir,
            execution_id=execution_id,
        )
        if workflow_result.request is not request:
            raise RuntimeError(
                "downstream workflow did not preserve comparison request"
            )
        if workflow_result.decomposition_result is not decomposition_result:
            raise RuntimeError(
                "downstream workflow did not preserve decomposition result"
            )
        if workflow_result.evidence_result is not acquisition.evidence_result:
            raise RuntimeError("downstream workflow did not preserve acquired evidence")

        return PatentMultiPatentFullWorkflowResult(
            request=request,
            acquisition=acquisition,
            decomposition_result=decomposition_result,
            workflow_result=workflow_result,
        )
