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
        == 3
    )
    assert (
        pipeline.source_searcher.search_budget
        .maximum_credits
        == 3.0
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


def test_live_runtime_accepts_semantic_citation_verifier() -> None:
    request = ResearchRequest(
        request_id="research-semantic-verifier",
        question="How does grounded research work?",
        objective="Explain grounded research.",
        maximum_sources=2,
    )
    verifier = object()

    pipeline = build_live_research_pipeline(
        request=request,
        search_config=TavilySearchConfig(
            api_key=SecretStr("test-secret"),
            maximum_results=10,
        ),
        semantic_citation_verifier=verifier,
    )

    assert pipeline.semantic_citation_verifier is verifier



def test_live_runtime_accepts_claim_relevance_evaluator() -> None:
    research_request = ResearchRequest(
        request_id="request-relevance-runtime",
        question="How can an agent bound model usage?",
        objective="Describe a concrete runtime usage control.",
        maximum_sources=1,
    )
    evaluator = object()

    pipeline = build_live_research_pipeline(
        request=research_request,
        search_config=TavilySearchConfig(
            api_key="test-key",
            maximum_results=3,
        ),
        claim_relevance_evaluator=evaluator,
    )

    assert pipeline.claim_relevance_evaluator is evaluator

def test_live_runtime_accepts_evidence_extractor_override() -> None:
    class StubEvidenceExtractor:
        def extract(self, document_set):  # type: ignore[no-untyped-def]
            raise AssertionError("not called in composition test")

    request = ResearchRequest(
        request_id="research-evidence-override",
        question="How does grounded research work?",
        objective="Explain grounded research.",
        maximum_sources=2,
    )
    override = StubEvidenceExtractor()

    pipeline = build_live_research_pipeline(
        request=request,
        search_config=TavilySearchConfig(
            api_key=SecretStr("test-secret"),
            maximum_results=10,
        ),
        evidence_extractor=override,
    )

    assert pipeline.evidence_extractor is override


def test_live_runtime_keeps_default_paragraph_evidence_extractor() -> None:
    request = ResearchRequest(
        request_id="research-default-evidence",
        question="How does grounded research work?",
        objective="Explain grounded research.",
        maximum_sources=2,
    )

    pipeline = build_live_research_pipeline(
        request=request,
        search_config=TavilySearchConfig(
            api_key=SecretStr("test-secret"),
            maximum_results=10,
        ),
    )

    assert isinstance(
        pipeline.evidence_extractor,
        PipelineEvidenceExtractorAdapter,
    )
    assert isinstance(
        pipeline.evidence_extractor.extractor,
        ParagraphEvidenceExtractor,
    )

def test_live_runtime_accepts_answer_coverage_evaluator() -> None:
    from app.schemas.research_request import ResearchRequest
    from app.schemas.tavily_search_config import TavilySearchConfig

    research_request = ResearchRequest(
        request_id="request-answer-coverage-runtime",
        question="How does the mechanism work?",
        objective="Explain the complete mechanism.",
        maximum_sources=1,
    )
    evaluator = object()

    pipeline = build_live_research_pipeline(
        request=research_request,
        search_config=TavilySearchConfig(
            api_key="test-key",
            maximum_results=3,
        ),
        answer_coverage_evaluator=evaluator,
    )

    assert pipeline.answer_coverage_evaluator is evaluator
