"""Runtime for mapping patent claim elements to traceable technical evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.research.patent_claim_decomposition_runtime import (
    PatentClaimDecompositionRuntimeResult,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PatentTechnicalRelevanceEvidenceResult,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentClaimElementEvidenceMapping,
    PatentClaimEvidenceMapping,
    PatentClaimsDocumentEvidenceMapping,
    PatentClaimSetEvidenceMapping,
    PatentPriorArtEvidenceEvaluation,
)
from app.schemas.research_evidence import ResearchEvidence


class PatentElementEvidenceRelevanceResultProtocol(Protocol):
    """Minimal result required from one element/evidence evaluator."""

    judgment: object


class PatentElementEvidenceRelevanceEvaluatorProtocol(Protocol):
    """Evaluate one technical claim element against one evidence excerpt."""

    def evaluate(
        self,
        *,
        element_text: str,
        evidence_excerpt: str,
    ) -> PatentElementEvidenceRelevanceResultProtocol: ...


@dataclass(frozen=True)
class PatentPriorArtEvidenceMappingRuntimeResult:
    """Inputs plus traceable element/evidence mapping documents."""

    decomposition_result: PatentClaimDecompositionRuntimeResult
    evidence_result: PatentTechnicalRelevanceEvidenceResult
    mapping_documents: tuple[PatentClaimsDocumentEvidenceMapping, ...]


class PatentPriorArtEvidenceMappingRuntime:
    """Map every decomposed claim element against every supplied evidence item."""

    def __init__(
        self,
        *,
        evaluator: PatentElementEvidenceRelevanceEvaluatorProtocol,
    ) -> None:
        self._evaluator = evaluator

    def map(
        self,
        *,
        decomposition_result: PatentClaimDecompositionRuntimeResult,
        evidence_result: PatentTechnicalRelevanceEvidenceResult,
    ) -> PatentPriorArtEvidenceMappingRuntimeResult:
        """Return ordered technical relevance mappings with exact provenance."""

        self._validate_request_binding(evidence_result)

        ordered_evidence = tuple(evidence_result.evidence_set.ordered_evidence())
        document_by_id = {
            document.document_id: document
            for document in evidence_result.document_set.documents
        }

        mapping_documents: list[PatentClaimsDocumentEvidenceMapping] = []

        for document in decomposition_result.decomposition_documents:
            mapped_sets: list[PatentClaimSetEvidenceMapping] = []

            for claim_set in document.claim_sets:
                mapped_claims: list[PatentClaimEvidenceMapping] = []

                for claim in claim_set.claims:
                    mapped_elements: list[PatentClaimElementEvidenceMapping] = []

                    for element in claim.elements:
                        evaluations = tuple(
                            self._evaluate_evidence(
                                element_text=element.text,
                                evidence=evidence,
                                document_by_id=document_by_id,
                            )
                            for evidence in ordered_evidence
                        )

                        mapped_elements.append(
                            PatentClaimElementEvidenceMapping(
                                element_number=element.element_number,
                                element_text=element.text,
                                evaluations=evaluations,
                            )
                        )

                    mapped_claims.append(
                        PatentClaimEvidenceMapping(
                            claim_number=claim.claim_number,
                            provider_position=claim.provider_position,
                            original_claim_text=claim.original_claim_text,
                            elements=tuple(mapped_elements),
                        )
                    )

                mapped_sets.append(
                    PatentClaimSetEvidenceMapping(
                        language=claim_set.language,
                        claims=tuple(mapped_claims),
                    )
                )

            mapping_documents.append(
                PatentClaimsDocumentEvidenceMapping(
                    publication_number=document.publication_number,
                    publication_docdb=document.publication_docdb,
                    source_endpoint=document.source_endpoint,
                    claim_sets=tuple(mapped_sets),
                )
            )

        return PatentPriorArtEvidenceMappingRuntimeResult(
            decomposition_result=decomposition_result,
            evidence_result=evidence_result,
            mapping_documents=tuple(mapping_documents),
        )

    @staticmethod
    def _validate_request_binding(
        evidence_result: PatentTechnicalRelevanceEvidenceResult,
    ) -> None:
        if (
            evidence_result.evidence_set.request_id
            != evidence_result.document_set.request_id
        ):
            raise RuntimeError(
                "patent evidence mapping input request IDs did not match"
            )

        if evidence_result.evidence_set.document_set != evidence_result.document_set:
            raise RuntimeError(
                "patent evidence mapping input did not preserve the document set"
            )

    def _evaluate_evidence(
        self,
        *,
        element_text: str,
        evidence: ResearchEvidence,
        document_by_id: dict[str, object],
    ) -> PatentPriorArtEvidenceEvaluation:
        document = document_by_id.get(evidence.document_id)
        if document is None:
            raise RuntimeError(
                "patent evidence mapping referenced an unknown evidence document"
            )

        candidate = document.candidate
        if candidate.source_id != evidence.source_id:
            raise RuntimeError("patent evidence mapping source identity did not match")

        publication_number = candidate.metadata.get("patent_publication_number")
        if publication_number is None or not publication_number.strip():
            raise RuntimeError(
                "patent evidence mapping source lacked publication identity"
            )

        generated = self._evaluator.evaluate(
            element_text=element_text,
            evidence_excerpt=evidence.excerpt,
        )

        return PatentPriorArtEvidenceEvaluation(
            publication_number=publication_number,
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            document_id=evidence.document_id,
            excerpt=evidence.excerpt,
            start_character=evidence.start_character,
            end_character=evidence.end_character,
            judgment=generated.judgment,
        )
