"""CLI handler for one approved federated Web and Local research execution."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI

from app.budget import ExecutionBudget
from app.config import Settings, load_settings
from app.rag.openai_embedding_provider import OpenAIEmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.hybrid_runtime import (
    build_hybrid_bounded_research_workers,
    legacy_compatible_role_policy,
)
from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.integrated_runtime import build_integrated_research_pipeline
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_adapter import (
    LocalDocumentAdapter,
    LocalDocumentBundle,
)
from app.research.local_external_send_approval import (
    INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
    LocalExternalSendApproval,
    LocalExternalSendApprovalGate,
)
from app.research.local_worker_runtime import (
    LocalWorkerSettings,
    load_local_worker_settings,
)
from app.research.openai_evidence_claim_generator import (
    OpenAIEvidenceClaimGenerator,
)
from app.research.openai_evidence_relevance_evaluator import (
    OpenAIEvidenceRelevanceEvaluator,
)
from app.research.paragraph_evidence_extractor import ParagraphEvidenceExtractor
from app.research.pipeline_analysis_adapters import (
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_source_adapters import PipelineSourceSearchAdapter
from app.research.research_result_guardrail import ResearchResultGuardrail
from app.research.research_result_writer import ResearchResultWriter
from app.research.research_source_type_classifier import (
    ResearchSourceTypeClassifier,
)
from app.research.semantic_evidence_reranker import SemanticEvidenceReranker
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.research.single_research_agent_pipeline import SingleResearchAgentPipeline
from app.research.tavily_research_source_search_tool import (
    TavilyResearchSourceSearchTool,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_budget import ResearchSearchBudget
from app.schemas.tavily_search_config import (
    TavilySearchConfig,
    load_tavily_search_config,
)
from app.services.openai_client import create_openai_client

INTEGRATED_CLAIM_GENERATION_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)
INTEGRATED_CLAIM_RELEVANCE_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)
INTEGRATED_EVIDENCE_RELEVANCE_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)


class IntegratedResearchHandler:
    """Run one approved semantic research request over Web and Local sources."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        config_loader: Callable[[], TavilySearchConfig] | None = None,
        settings_loader: Callable[[], Settings] | None = None,
        openai_client_factory: Callable[[Settings], OpenAI] | None = None,
        local_worker_settings_loader: Callable[[], LocalWorkerSettings] | None = None,
        document_adapter: LocalDocumentAdapter | None = None,
        writer: ResearchResultWriter | None = None,
        guardrail: ResearchResultGuardrail | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._id_factory = id_factory or self._default_id
        self._config_loader = config_loader or self._load_config
        self._settings_loader = settings_loader or load_settings
        self._openai_client_factory = openai_client_factory or create_openai_client
        self._local_worker_settings_loader = (
            local_worker_settings_loader or load_local_worker_settings
        )
        self._document_adapter = document_adapter or LocalDocumentAdapter()
        self._writer = writer or ResearchResultWriter()
        self._guardrail = guardrail or ResearchResultGuardrail()
        self._stdout = stdout or sys.stdout

    def __call__(
        self,
        question: str,
        objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        maximum_sources: int,
        maximum_bytes: int,
        output_dir: Path,
        access_policy: LocalDocumentAccessPolicy,
        approval: LocalExternalSendApproval | None,
    ) -> int:
        execution_id = self._id_factory().strip()
        if not execution_id:
            raise RuntimeError(
                "integrated research execution ID factory returned blank value"
            )

        approval_gate = LocalExternalSendApprovalGate()
        approval_gate.validate(
            approval,
            sources,
            purpose=INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
        )
        bundle = self._document_adapter.load_validated(sources)
        access_gate = LocalDocumentAccessGate(access_policy)
        fresh_sources = tuple(
            access_gate.validate(source.resolved_path) for source in sources
        )
        approval_gate.validate(
            approval,
            fresh_sources,
            purpose=INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
        )

        request = ResearchRequest(
            request_id=execution_id,
            question=question,
            objective=objective,
            maximum_sources=maximum_sources,
            metadata={"mode": "integrated-web-local-cli"},
        )
        pipeline = self._build_pipeline(
            request=request,
            bundle=bundle,
            question=question,
            objective=objective,
            maximum_bytes=maximum_bytes,
        )
        result = pipeline.run(request, workspace_id=f"{execution_id}-workspace")
        self._guardrail.validate(result, execution_id=execution_id)
        paths = self._writer.write(
            result,
            output_dir=output_dir,
            execution_id=execution_id,
        )
        print(f"AIRA integrated report: {paths.report_path}", file=self._stdout)
        print(f"AIRA integrated result: {paths.result_path}", file=self._stdout)
        return 0

    def _build_pipeline(
        self,
        *,
        request: ResearchRequest,
        bundle: LocalDocumentBundle,
        question: str,
        objective: str,
        maximum_bytes: int,
    ) -> SingleResearchAgentPipeline:
        search_config = self._config_loader()
        settings = self._settings_loader()
        openai_client = self._openai_client_factory(settings)
        local_worker_settings = self._local_worker_settings_loader()
        role_policy = legacy_compatible_role_policy(
            local_worker_settings=local_worker_settings
        )
        bounded_workers = build_hybrid_bounded_research_workers(
            role_policy=role_policy,
            local_worker_settings=local_worker_settings,
            openai_client=openai_client,
            openai_model=settings.openai_model,
            claim_relevance_budget=INTEGRATED_CLAIM_RELEVANCE_BUDGET,
        )
        evidence_extractor = PipelineEvidenceExtractorAdapter(
            SemanticResearchEvidenceExtractor(
                question=question,
                objective=objective,
                paragraph_extractor=ParagraphEvidenceExtractor(),
                shortlister=EmbeddingSemanticEvidenceShortlister(
                    embedding_provider=OpenAIEmbeddingProvider(client=openai_client)
                ),
                reranker=SemanticEvidenceReranker(
                    evaluator=OpenAIEvidenceRelevanceEvaluator(
                        client=openai_client,
                        model=settings.openai_model,
                    ),
                    budget=INTEGRATED_EVIDENCE_RELEVANCE_BUDGET,
                ),
            )
        )
        claim_builder = GenerativePipelineClaimBuilder(
            generator=OpenAIEvidenceClaimGenerator(
                client=openai_client,
                model=settings.openai_model,
            ),
            budget=INTEGRATED_CLAIM_GENERATION_BUDGET,
        )
        candidate_count = min(
            search_config.maximum_results,
            request.maximum_sources * 3,
        )
        search_budget = ResearchSearchBudget(
            maximum_provider_calls=3,
            maximum_credits=3.0,
            maximum_latency_ms=int(search_config.timeout_seconds * 1000) * 3,
        )
        web_searcher = PipelineSourceSearchAdapter(
            TavilyResearchSourceSearchTool(
                config=search_config.model_copy(
                    update={"maximum_results": candidate_count}
                ),
                source_type_classifier=ResearchSourceTypeClassifier(
                    official_documentation_hosts=frozenset({"openai.github.io"})
                ),
            ),
            maximum_candidates=candidate_count,
            minimum_results_per_query=candidate_count,
            budget=search_budget,
        )
        local_searcher = PipelineSourceSearchAdapter(
            InMemoryResearchSourceSearchTool(records=bundle.source_records),
            maximum_candidates=candidate_count,
        )
        return build_integrated_research_pipeline(
            web_searcher=web_searcher,
            local_searcher=local_searcher,
            web_reader=HttpHtmlResearchSourceReader(
                config=HttpHtmlReaderConfig(maximum_bytes=maximum_bytes)
            ),
            local_reader=InMemoryResearchSourceReader(records=bundle.document_records),
            evidence_extractor=evidence_extractor,
            claim_builder=claim_builder,
            semantic_citation_verifier=bounded_workers.semantic_citation_verifier,
            claim_relevance_evaluator=bounded_workers.claim_relevance_evaluator,
            answer_coverage_evaluator=bounded_workers.answer_coverage_evaluator,
            maximum_documents=request.maximum_sources,
        )

    @staticmethod
    def _load_config() -> TavilySearchConfig:
        load_dotenv()
        return load_tavily_search_config()

    @staticmethod
    def _default_id() -> str:
        return f"aira-integrated-{uuid4().hex}"
