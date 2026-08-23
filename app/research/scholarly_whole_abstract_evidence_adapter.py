"""Create one exact non-semantic evidence item per scholarly abstract."""

from __future__ import annotations

from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_source_document import ResearchSourceDocument
from app.schemas.scholarly_document_adaptation import ScholarlyDocumentAdaptation
from app.schemas.scholarly_evidence_adaptation import ScholarlyEvidenceAdaptation


class ScholarlyWholeAbstractEvidenceAdapter:
    """Adapt exact abstract documents without relevance judgment."""

    @property
    def name(self) -> str:
        return "scholarly-whole-abstract-evidence-adapter"

    def adapt(
        self,
        document_adaptation: ScholarlyDocumentAdaptation,
    ) -> ScholarlyEvidenceAdaptation:
        evidence = [
            self._evidence(document)
            for document in document_adaptation.document_set.documents
        ]
        evidence_set = ResearchEvidenceSet(
            request_id=document_adaptation.document_set.request_id,
            document_set=document_adaptation.document_set,
            evidence=evidence,
        )
        return ScholarlyEvidenceAdaptation(
            document_adaptation=document_adaptation,
            evidence_set=evidence_set,
        )

    def _evidence(self, document: ResearchSourceDocument) -> ResearchEvidence:
        if len(document.sections) != 1:
            raise ValueError("scholarly abstract document requires one section")
        section = document.sections[0]
        if section.start_character != 0 or section.end_character != len(
            document.content
        ):
            raise ValueError("scholarly abstract section must cover the whole document")
        if section.content != document.content:
            raise ValueError("scholarly abstract section must equal document content")
        candidate = document.candidate
        metadata = {
            key: value
            for key, value in document.metadata.items()
            if key.startswith("scholarly_")
        }
        metadata.update(
            {
                "adapter": self.name,
                "evidence_scope": "provider_supplied_abstract_only",
                "relevance_assessment": "not_performed",
                "confidence_assessment": "not_performed",
                "paper_quality_assessment": "not_performed",
                "citation_impact_assessment": "not_performed",
            }
        )
        return ResearchEvidence(
            evidence_id=f"{document.document_id}-whole-abstract-evidence",
            request_id=candidate.request_id,
            task_id=candidate.task_id,
            source_id=candidate.source_id,
            document_id=document.document_id,
            section_id=section.section_id,
            excerpt=document.content,
            start_character=0,
            end_character=len(document.content),
            evidence_type=ResearchEvidenceType.OTHER,
            stance=ResearchEvidenceStance.NEUTRAL,
            relevance_score=0.0,
            confidence_score=0.0,
            rationale=(
                "The complete provider-supplied abstract is preserved without "
                "semantic relevance, support, or paper-quality judgment."
            ),
            metadata=metadata,
        )
