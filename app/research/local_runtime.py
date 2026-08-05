"""Local-document runtime composition for AIRA."""

from __future__ import annotations

from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.local_document_adapter import LocalDocumentBundle
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_compatibility import (
    PipelineQueryPlannerAdapter,
    PipelineTaskDecomposerAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.research_evidence_extractor import (
    ResearchEvidenceExtractor,
)
from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
    ResearchSourceQualityLevel,
)


class WholeDocumentEvidenceExtractor(
    ResearchEvidenceExtractor
):
    """Treat each readable local document as traceable evidence."""

    @property
    def name(self) -> str:
        """Return the extractor name."""

        return "whole-local-document"

    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        """Extract the complete document as one evidence item."""

        candidate = document.candidate
        evidence = ResearchEvidence(
            evidence_id=f"{document.document_id}-evidence-001",
            request_id=candidate.request_id,
            task_id=candidate.task_id,
            source_id=candidate.source_id,
            document_id=document.document_id,
            excerpt=document.content,
            start_character=0,
            end_character=len(document.content),
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=1.0,
            confidence_score=0.8,
            rationale=(
                "The evidence is the complete readable local "
                "document selected by the research query."
            ),
            metadata={
                "extractor": self.name,
            },
        )

        return ResearchEvidenceExtractionResult(
            document=document,
            status=ResearchEvidenceExtractionStatus.SUCCEEDED,
            extractor=self.name,
            evidence=[evidence],
            duration_ms=0,
            metadata={
                "mode": "whole-document",
            },
        )


class LocalDocumentSourceQualityEvaluator:
    """Apply a conservative deterministic quality assessment."""

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        """Evaluate one local source without claiming authority."""

        return ResearchSourceQualityEvaluation(
            document=document,
            evaluator="local-document-quality",
            authority_score=0.5,
            primary_source_score=0.5,
            recency_score=0.5,
            completeness_score=1.0,
            traceability_score=1.0,
            overall_score=0.7,
            quality_level=ResearchSourceQualityLevel.HIGH,
        )


def build_local_research_pipeline(
    bundle: LocalDocumentBundle,
) -> SingleResearchAgentPipeline:
    """Compose the single-agent pipeline for local documents."""

    search_tool = InMemoryResearchSourceSearchTool(
        records=bundle.source_records
    )
    source_reader = InMemoryResearchSourceReader(
        records=bundle.document_records
    )

    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=PipelineSourceSearchAdapter(
            search_tool
        ),
        source_reader=PipelineSourceReaderAdapter(
            source_reader
        ),
        evidence_extractor=PipelineEvidenceExtractorAdapter(
            WholeDocumentEvidenceExtractor()
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=(
            LocalDocumentSourceQualityEvaluator()
        ),
    )
