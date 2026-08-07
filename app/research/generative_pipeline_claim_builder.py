"""Generative claim builder for the single-agent research pipeline."""

from __future__ import annotations

from typing import Protocol

from app.research.openai_evidence_claim_generator import (
    GeneratedClaimProposalResult,
)
from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
    ResearchClaimSet,
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
)


class EvidenceClaimGeneratorProtocol(Protocol):
    """Generate one claim proposal from one evidence item."""

    def generate(
        self,
        evidence: ResearchEvidence,
    ) -> GeneratedClaimProposalResult: ...


class GenerativePipelineClaimBuilder:
    """Build traceable draft claims from generated claim proposals."""

    def __init__(
        self,
        *,
        generator: EvidenceClaimGeneratorProtocol,
    ) -> None:
        self._generator = generator

    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet:
        """Generate one traceable draft claim per evidence item."""

        claims = [
            self._claim(
                evidence=evidence,
                position=position,
            )
            for position, evidence in enumerate(
                evidence_set.ordered_evidence(),
                start=1,
            )
        ]

        return ResearchClaimSet(
            request_id=evidence_set.request_id,
            evidence_set=evidence_set,
            claims=claims,
        )

    def _claim(
        self,
        *,
        evidence: ResearchEvidence,
        position: int,
    ) -> ResearchClaim:
        """Generate one claim while preserving deterministic provenance."""

        result = self._generator.generate(evidence)
        proposal = result.proposal

        citation = ResearchCitation(
            citation_id=(
                f"{evidence.request_id}-citation-"
                f"{position:03d}"
            ),
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            document_id=evidence.document_id,
            excerpt=evidence.excerpt,
            start_character=evidence.start_character,
            end_character=evidence.end_character,
            metadata={
                "builder": "generative-pipeline",
            },
        )

        metadata = {
            "builder": "generative-pipeline",
            "generator_response_id": result.response_id,
        }

        if result.request_id is not None:
            metadata["generator_request_id"] = result.request_id

        return ResearchClaim(
            claim_id=(
                f"{evidence.request_id}-claim-"
                f"{position:03d}"
            ),
            request_id=evidence.request_id,
            task_id=evidence.task_id,
            text=proposal.text,
            claim_type=ResearchClaimType.FACTUAL,
            status=ResearchClaimStatus.DRAFT,
            confidence_score=evidence.confidence_score,
            citations=[citation],
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            rationale=proposal.rationale,
            metadata=metadata,
        )
