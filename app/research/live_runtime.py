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
from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchRequest
from app.schemas.tavily_search_config import TavilySearchConfig


def build_live_research_pipeline(
    *,
    request: ResearchRequest,
    search_config: TavilySearchConfig,
    reader_config: HttpHtmlReaderConfig | None = None,
) -> SingleResearchAgentPipeline:
    """Compose deterministic planning with live search and reading."""

    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=PipelineSourceSearchAdapter(
            TavilyResearchSourceSearchTool(
                config=search_config.model_copy(
                    update={
                        "maximum_results": min(
                            search_config.maximum_results,
                            request.maximum_sources,
                        )
                    }
                )
            ),
            maximum_candidates=request.maximum_sources,
        ),
        source_reader=PipelineSourceReaderAdapter(
            HttpHtmlResearchSourceReader(
                config=reader_config
                or HttpHtmlReaderConfig()
            )
        ),
        evidence_extractor=PipelineEvidenceExtractorAdapter(
            ParagraphEvidenceExtractor()
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=(
            LiveWebSourceQualityEvaluator()
        ),
    )
