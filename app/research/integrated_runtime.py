"""Deterministic composition for one federated Web and Local execution."""

from __future__ import annotations

from app.research.federated_research_source_searcher import (
    FederatedResearchSourceSearcher,
)
from app.research.integrated_source_diversity_document_selector import (
    IntegratedSourceDiversityDocumentSelector,
)
from app.research.live_source_quality_evaluator import (
    LiveWebSourceQualityEvaluator,
)
from app.research.local_runtime import (
    LocalDocumentSourceQualityEvaluator,
    WholeDocumentEvidenceExtractor,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_compatibility import (
    PipelineQueryPlannerAdapter,
    PipelineTaskDecomposerAdapter,
)
from app.research.pipeline_source_adapters import PipelineSourceReaderAdapter
from app.research.research_request_validator import ResearchRequestValidator
from app.research.research_source_reader import ResearchSourceReader
from app.research.routing_research_source_quality_evaluator import (
    RoutingResearchSourceQualityEvaluator,
)
from app.research.routing_research_source_reader import (
    RoutingResearchSourceReader,
)
from app.research.single_research_agent_pipeline import (
    AnswerCoverageEvaluationServiceProtocol,
    ClaimRelevanceEvaluationServiceProtocol,
    ResearchClaimBuilderProtocol,
    ResearchDocumentSelectionProtocol,
    ResearchEvidenceExtractorProtocol,
    ResearchSourceQualityEvaluatorProtocol,
    ResearchSourceSearcherProtocol,
    SemanticCitationVerifierProtocol,
    SingleResearchAgentPipeline,
)


def build_integrated_research_pipeline(
    *,
    web_searcher: ResearchSourceSearcherProtocol,
    local_searcher: ResearchSourceSearcherProtocol,
    web_reader: ResearchSourceReader,
    local_reader: ResearchSourceReader,
    evidence_extractor: ResearchEvidenceExtractorProtocol | None = None,
    claim_builder: ResearchClaimBuilderProtocol | None = None,
    web_quality_evaluator: ResearchSourceQualityEvaluatorProtocol | None = None,
    local_quality_evaluator: ResearchSourceQualityEvaluatorProtocol | None = None,
    document_selector: ResearchDocumentSelectionProtocol | None = None,
    semantic_citation_verifier: SemanticCitationVerifierProtocol | None = None,
    claim_relevance_evaluator: ClaimRelevanceEvaluationServiceProtocol | None = None,
    answer_coverage_evaluator: AnswerCoverageEvaluationServiceProtocol | None = None,
    maximum_documents: int | None = None,
) -> SingleResearchAgentPipeline:
    """Build one existing pipeline over federated source universes."""
    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=FederatedResearchSourceSearcher(
            web_searcher=web_searcher,
            local_searcher=local_searcher,
        ),
        source_reader=PipelineSourceReaderAdapter(
            RoutingResearchSourceReader(
                web_reader=web_reader,
                local_reader=local_reader,
            )
        ),
        evidence_extractor=(
            evidence_extractor
            or PipelineEvidenceExtractorAdapter(WholeDocumentEvidenceExtractor())
        ),
        claim_builder=(claim_builder or DeterministicPipelineClaimBuilder()),
        source_quality_evaluator=(
            RoutingResearchSourceQualityEvaluator(
                web_evaluator=(
                    web_quality_evaluator or LiveWebSourceQualityEvaluator()
                ),
                local_evaluator=(
                    local_quality_evaluator or LocalDocumentSourceQualityEvaluator()
                ),
            )
        ),
        document_selector=(
            document_selector
            or (
                IntegratedSourceDiversityDocumentSelector(
                    maximum_documents=maximum_documents
                )
                if maximum_documents is not None
                else None
            )
        ),
        semantic_citation_verifier=semantic_citation_verifier,
        claim_relevance_evaluator=claim_relevance_evaluator,
        answer_coverage_evaluator=answer_coverage_evaluator,
        collect_run_metrics=True,
    )
