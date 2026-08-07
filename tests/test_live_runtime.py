"""Tests for live research runtime composition."""

from pydantic import SecretStr

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.live_runtime import (
    build_live_research_pipeline,
)
from app.research.live_source_quality_evaluator import (
    LiveWebSourceQualityEvaluator,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.pipeline_analysis_adapters import (
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.quality_aware_document_selector import (
    QualityAwareDocumentSelector,
)
from app.research.supplemental_research_query_planner import (
    SupplementalResearchQueryPlanner,
)
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_budget import (
    ResearchSearchBudget,
)
from app.schemas.tavily_search_config import TavilySearchConfig


def test_live_runtime_composes_live_adapters() -> None:
    request = ResearchRequest(
        request_id="research-001",
        question="How does grounded research work?",
        objective="Explain grounded research.",
        maximum_sources=3,
    )
    pipeline = build_live_research_pipeline(
        request=request,
        search_config=TavilySearchConfig(
            api_key=SecretStr("test-secret"),
            maximum_results=10,
        ),
    )

    assert isinstance(
        pipeline.source_searcher,
        PipelineSourceSearchAdapter,
    )
    assert isinstance(
        pipeline.source_searcher.search_tool,
        TavilyResearchSourceSearchTool,
    )
    assert pipeline.source_searcher.search_budget is not None
    assert (
        pipeline.source_searcher.search_budget
        .maximum_provider_calls
        == 2
    )
    assert (
        pipeline.source_searcher.search_budget
        .maximum_credits
        == 2.0
    )
    assert isinstance(
        pipeline.source_reader,
        PipelineSourceReaderAdapter,
    )
    assert isinstance(
        pipeline.source_reader.reader,
        HttpHtmlResearchSourceReader,
    )
    assert isinstance(
        pipeline.evidence_extractor,
        PipelineEvidenceExtractorAdapter,
    )
    assert isinstance(
        pipeline.evidence_extractor.extractor,
        ParagraphEvidenceExtractor,
    )
    assert isinstance(
        pipeline.source_quality_evaluator,
        LiveWebSourceQualityEvaluator,
    )
    assert isinstance(
        pipeline.document_selector,
        QualityAwareDocumentSelector,
    )
    assert pipeline.document_selector.maximum_documents == 3
    assert isinstance(
        pipeline.supplemental_query_planner,
        SupplementalResearchQueryPlanner,
    )


def test_live_runtime_accepts_custom_search_budget() -> None:
    request = ResearchRequest(
        request_id="research-custom-budget",
        question="How does grounded research work?",
        objective="Explain grounded research.",
        maximum_sources=3,
    )
    budget = ResearchSearchBudget(
        maximum_provider_calls=1,
        maximum_credits=0.5,
        maximum_latency_ms=1_500,
        default_credit_per_call=0.5,
    )

    pipeline = build_live_research_pipeline(
        request=request,
        search_config=TavilySearchConfig(
            api_key=SecretStr("test-secret"),
            maximum_results=10,
        ),
        search_budget=budget,
    )

    assert pipeline.source_searcher.search_budget == budget
