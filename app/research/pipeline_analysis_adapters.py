"""Evidence and claim components for the research pipeline."""

from __future__ import annotations

from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.research.research_evidence_extractor_validator import (
    ResearchEvidenceExtractorValidator,
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
    ResearchEvidenceStance,
)
from app.schemas.research_source_document import (
    ResearchSourceDocumentSet,
)


class PipelineEvidenceExtractorAdapter:
    """Run a single-document extractor across a document set."""

    def __init__(
        self,
        extractor: ResearchEvidenceExtractor,
        *,
        validator: ResearchEvidenceExtractorValidator | None = None,
    ) -> None:
        self._extractor = extractor
        self._validator = (
            validator or ResearchEvidenceExtractorValidator()
        )
        self._validator.validate_extractor(extractor)

    @property
    def extractor(self) -> ResearchEvidenceExtractor:
        """Return the wrapped evidence extractor."""

        return self._extractor

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        """Extract and combine evidence from readable documents."""

        evidence: list[ResearchEvidence] = []

        for document in document_set.successful_documents():
            result = self._extractor.extract(document)
            self._validator.validate_result(
                extractor=self._extractor,
                document=document,
                result=result,
            )
            evidence.extend(result.ordered_evidence())

        return ResearchEvidenceSet(
            request_id=document_set.request_id,
            document_set=document_set,
            evidence=evidence,
        )


class DeterministicPipelineClaimBuilder:
    """Build one traceable claim from each evidence item."""

    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet:
        """Convert evidence into deterministic research claims."""

        claims = [
            self._claim(
                evidence=item,
                position=position,
            )
            for position, item in enumerate(
                evidence_set.ordered_evidence(),
                start=1,
            )
        ]

        return ResearchClaimSet(
            request_id=evidence_set.request_id,
            evidence_set=evidence_set,
            claims=claims,
        )

    @staticmethod
    def _claim(
        *,
        evidence: ResearchEvidence,
        position: int,
    ) -> ResearchClaim:
        """Build one claim and citation from evidence."""

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
                "builder": "deterministic-pipeline",
            },
        )

        supporting_ids: list[str] = []
        contradicting_ids: list[str] = []
        status = ResearchClaimStatus.DRAFT

        if evidence.stance is ResearchEvidenceStance.SUPPORTS:
            supporting_ids.append(evidence.evidence_id)
            status = ResearchClaimStatus.SUPPORTED
        elif (
            evidence.stance
            is ResearchEvidenceStance.CONTRADICTS
        ):
            contradicting_ids.append(evidence.evidence_id)
            status = ResearchClaimStatus.CONTESTED

        return ResearchClaim(
            claim_id=(
                f"{evidence.request_id}-claim-"
                f"{position:03d}"
            ),
            request_id=evidence.request_id,
            task_id=evidence.task_id,
            text=evidence.excerpt,
            claim_type=ResearchClaimType.FACTUAL,
            status=status,
            confidence_score=evidence.confidence_score,
            citations=[citation],
            supporting_evidence_ids=supporting_ids,
            contradicting_evidence_ids=contradicting_ids,
            rationale=(
                evidence.rationale
                or "Claim derived directly from traceable evidence."
            ),
            metadata={
                "builder": "deterministic-pipeline",
            },
        )
