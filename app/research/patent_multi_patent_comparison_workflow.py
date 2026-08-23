"""Bounded downstream workflow for one prepared patent comparison."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.research.patent_claim_chart_runtime import (
    PatentClaimChartRuntime,
    PatentClaimChartRuntimeResult,
)
from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntimeResult,
)
from app.research.patent_multi_patent_comparison_runtime import (
    PatentMultiPatentComparisonRuntime,
    PatentMultiPatentComparisonRuntimeResult,
)
from app.research.patent_multi_patent_comparison_writer import (
    PatentMultiPatentComparisonArtifactPaths,
    PatentMultiPatentComparisonWriter,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntime,
    PatentPriorArtEvidenceMappingRuntimeResult,
)
from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


@dataclass(frozen=True)
class PatentMultiPatentComparisonWorkflowResult:
    """All preserved stages and persisted artifacts from one bounded workflow."""

    request: PatentMultiPatentComparisonRequest
    decomposition_result: PatentClaimDecompositionRuntimeResult
    evidence_result: PatentTechnicalRelevanceEvidenceResult
    mapping_result: PatentPriorArtEvidenceMappingRuntimeResult
    chart_result: PatentClaimChartRuntimeResult
    comparison_result: PatentMultiPatentComparisonRuntimeResult
    artifact_paths: PatentMultiPatentComparisonArtifactPaths
    actual_mapping_calls: int


class PatentMultiPatentComparisonWorkflow:
    """Validate prepared inputs before mapping, comparison, and persistence."""

    def __init__(
        self,
        *,
        mapping_runtime: PatentPriorArtEvidenceMappingRuntime,
        chart_runtime: PatentClaimChartRuntime | None = None,
        comparison_runtime: PatentMultiPatentComparisonRuntime | None = None,
        writer: PatentMultiPatentComparisonWriter | None = None,
    ) -> None:
        self._mapping_runtime = mapping_runtime
        self._chart_runtime = chart_runtime or PatentClaimChartRuntime()
        self._comparison_runtime = (
            comparison_runtime or PatentMultiPatentComparisonRuntime()
        )
        self._writer = writer or PatentMultiPatentComparisonWriter()

    def execute(
        self,
        request: PatentMultiPatentComparisonRequest,
        *,
        decomposition_result: PatentClaimDecompositionRuntimeResult,
        evidence_result: PatentTechnicalRelevanceEvidenceResult,
        output_dir: Path,
        execution_id: str,
    ) -> PatentMultiPatentComparisonWorkflowResult:
        """Run only after all cost and identity preflight checks pass."""

        if not isinstance(request, PatentMultiPatentComparisonRequest):
            raise TypeError("request must be a PatentMultiPatentComparisonRequest")
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir must be a Path")

        element_count = self._validate_decomposition(request, decomposition_result)
        evidence_count = self._validate_evidence(request, evidence_result)
        actual_mapping_calls = element_count * evidence_count
        if actual_mapping_calls > request.maximum_mapping_calls:
            raise RuntimeError(
                "prepared element/evidence pairs exceed maximum_mapping_calls"
            )

        mapping_result = self._mapping_runtime.map(
            decomposition_result=decomposition_result,
            evidence_result=evidence_result,
        )
        if mapping_result.decomposition_result is not decomposition_result:
            raise RuntimeError("mapping runtime did not preserve decomposition result")
        if mapping_result.evidence_result is not evidence_result:
            raise RuntimeError("mapping runtime did not preserve evidence result")

        chart_result = self._chart_runtime.build(mapping_result)
        if chart_result.mapping_result is not mapping_result:
            raise RuntimeError("claim chart runtime did not preserve mapping result")

        comparison_result = self._comparison_runtime.build(chart_result)
        if comparison_result.chart_result is not chart_result:
            raise RuntimeError("comparison runtime did not preserve chart result")
        if len(comparison_result.comparisons) != 1:
            raise RuntimeError("workflow requires exactly one comparison artifact")

        comparison = comparison_result.comparisons[0]
        if comparison.target_publication_number != request.target_publication_number:
            raise RuntimeError("comparison target publication identity drifted")
        if comparison.prior_art_publications != request.comparison_publication_numbers:
            raise RuntimeError("comparison publication axis drifted")

        artifact_paths = self._writer.write(
            comparison,
            output_dir=output_dir,
            execution_id=execution_id,
        )
        return PatentMultiPatentComparisonWorkflowResult(
            request=request,
            decomposition_result=decomposition_result,
            evidence_result=evidence_result,
            mapping_result=mapping_result,
            chart_result=chart_result,
            comparison_result=comparison_result,
            artifact_paths=artifact_paths,
            actual_mapping_calls=actual_mapping_calls,
        )

    @staticmethod
    def _validate_decomposition(
        request: PatentMultiPatentComparisonRequest,
        result: PatentClaimDecompositionRuntimeResult,
    ) -> int:
        documents = result.decomposition_documents
        if len(documents) != 1:
            raise RuntimeError("workflow requires exactly one target claim document")
        document = documents[0]
        if (
            normalize_patent_publication_number(document.publication_number)
            != request.target_publication_number
        ):
            raise RuntimeError(
                "prepared target publication identity did not match request"
            )
        if len(document.claim_sets) != 1:
            raise RuntimeError(
                "workflow requires exactly one selected claim-language set"
            )
        claim_set = document.claim_sets[0]
        if claim_set.language.upper() != request.claim_language:
            raise RuntimeError("prepared claim language did not match request")
        if len(claim_set.claims) != 1:
            raise RuntimeError("workflow requires exactly one selected target claim")
        claim = claim_set.claims[0]
        if claim.claim_number != request.claim_number:
            raise RuntimeError("prepared claim number did not match request")
        element_count = len(claim.elements)
        if element_count > request.maximum_claim_elements:
            raise RuntimeError("prepared claim exceeds maximum_claim_elements")
        return element_count

    @staticmethod
    def _validate_evidence(
        request: PatentMultiPatentComparisonRequest,
        result: PatentTechnicalRelevanceEvidenceResult,
    ) -> int:
        ordered_evidence = tuple(result.evidence_set.ordered_evidence())
        if len(ordered_evidence) != len(request.comparison_publication_numbers):
            raise RuntimeError(
                "workflow requires exactly one evidence passage per comparison publication"
            )
        documents = {
            document.document_id: document for document in result.document_set.documents
        }
        publications: list[str] = []
        for evidence in ordered_evidence:
            document = documents.get(evidence.document_id)
            if document is None:
                raise RuntimeError("prepared evidence referenced an unknown document")
            publication_number = document.candidate.metadata.get(
                "patent_publication_number"
            )
            if publication_number is None:
                raise RuntimeError(
                    "prepared evidence document lacked publication identity"
                )
            publications.append(normalize_patent_publication_number(publication_number))
        if tuple(publications) != request.comparison_publication_numbers:
            raise RuntimeError(
                "prepared evidence publication order did not match request"
            )
        return len(ordered_evidence)
