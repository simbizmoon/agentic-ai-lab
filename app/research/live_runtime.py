"""Live web research runtime composition for AIRA."""

from __future__ import annotations

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.live_source_quality_evaluator import (
    LiveWebSourceQualityEvaluator,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
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
from app.research.quality_aware_document_selector import (
    QualityAwareDocumentSelector,
)
from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.research.research_source_type_classifier import (
    ResearchSourceTypeClassifier,
)
from app.research.single_research_agent_pipeline import (
    AnswerCoverageEvaluationServiceProtocol,
    ClaimRelevanceEvaluationServiceProtocol,
    ResearchClaimBuilderProtocol,
    ResearchEvidenceExtractorProtocol,
    SemanticCitationVerifierProtocol,
    SingleResearchAgentPipeline,
)
from app.research.supplemental_research_query_planner import (
    SupplementalResearchQueryPlanner,
)
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_budget import (
    ResearchSearchBudget,
)
from app.schemas.tavily_search_config import TavilySearchConfig


def build_live_research_pipeline(
    *,
    request: ResearchRequest,
    search_config: TavilySearchConfig,
    reader_config: HttpHtmlReaderConfig | None = None,
    search_budget: ResearchSearchBudget | None = None,
    semantic_citation_verifier: (
        SemanticCitationVerifierProtocol | None
    ) = None,
    claim_relevance_evaluator: (
        ClaimRelevanceEvaluationServiceProtocol | None
    ) = None,
    answer_coverage_evaluator: (
        AnswerCoverageEvaluationServiceProtocol | None
    ) = None,
    claim_builder: ResearchClaimBuilderProtocol | None = None,
    evidence_extractor: ResearchEvidenceExtractorProtocol | None = None,
) -> SingleResearchAgentPipeline:
    """Compose deterministic planning with live search and reading."""

    search_candidate_count = min(
        search_config.maximum_results,
        request.maximum_sources * 3,
    )

    resolved_search_budget = (
        search_budget
        or ResearchSearchBudget(
            maximum_provider_calls=2,
            maximum_credits=2.0,
            maximum_latency_ms=(
                int(search_config.timeout_seconds * 1000)
                * 2
            ),
        )
    )

    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=PipelineSourceSearchAdapter(
            TavilyResearchSourceSearchTool(
                config=search_config.model_copy(
                    update={
                        "maximum_results": search_candidate_count,
                    }
                ),
                source_type_classifier=(
                    ResearchSourceTypeClassifier(
                        official_documentation_hosts=(
                            frozenset({"openai.github.io"})
                        )
                    )
                ),
            ),
            maximum_candidates=search_candidate_count,
            minimum_results_per_query=search_candidate_count,
            budget=resolved_search_budget,
        ),
        source_reader=PipelineSourceReaderAdapter(
            HttpHtmlResearchSourceReader(
                config=reader_config
                or HttpHtmlReaderConfig()
            )
        ),
        evidence_extractor=(
            evidence_extractor
            or PipelineEvidenceExtractorAdapter(
                ParagraphEvidenceExtractor()
            )
        ),
        claim_builder=(
            claim_builder
            or DeterministicPipelineClaimBuilder()
        ),
        source_quality_evaluator=(
            LiveWebSourceQualityEvaluator()
        ),
        document_selector=QualityAwareDocumentSelector(
            maximum_documents=request.maximum_sources
        ),
        supplemental_query_planner=(
            SupplementalResearchQueryPlanner()
        ),
        semantic_citation_verifier=(
            semantic_citation_verifier
        ),
        claim_relevance_evaluator=(
            claim_relevance_evaluator
        ),
        answer_coverage_evaluator=(
            answer_coverage_evaluator
        ),
    )
