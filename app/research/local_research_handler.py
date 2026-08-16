"""Default CLI handler for local-document research."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from openai import OpenAI

from app.budget import ExecutionBudget
from app.config import Settings, load_settings
from app.rag.caching_embedding_provider import (
    CachingEmbeddingProvider,
)
from app.rag.embedding_cache_directory import (
    resolve_embedding_cache_directory,
)
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)
from app.research.caching_local_document_parser import CachingLocalDocumentParser
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.hybrid_runtime import (
    build_hybrid_bounded_research_workers,
    legacy_compatible_role_policy,
)
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_adapter import (
    LocalDocumentAdapter,
    LocalDocumentBundle,
)
from app.research.local_document_parser import LocalDocumentParser
from app.research.local_external_send_approval import (
    LocalExternalSendApproval,
    LocalExternalSendApprovalGate,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
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
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.parsed_document_cache import ParsedDocumentCache
from app.research.parsed_document_cache_directory import (
    resolve_parsed_document_cache_directory,
)
from app.research.pipeline_analysis_adapters import (
    PipelineEvidenceExtractorAdapter,
)
from app.research.research_result_guardrail import (
    ResearchResultGuardrail,
)
from app.research.research_result_writer import (
    ResearchResultWriter,
)
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
)
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.services.openai_client import create_openai_client

LOCAL_CLAIM_GENERATION_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)

LOCAL_CLAIM_RELEVANCE_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)

LOCAL_EVIDENCE_RELEVANCE_BUDGET = ExecutionBudget(
    max_attempts=8,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)

DEFAULT_MAXIMUM_LOCAL_SOURCE_BYTES = 32 * 1024 * 1024


class LocalResearchHandler:
    """Execute local research and persist its results."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        writer: ResearchResultWriter | None = None,
        guardrail: ResearchResultGuardrail | None = None,
        stdout: TextIO | None = None,
        parsed_cache_directory_resolver: Callable[[], Path] | None = None,
        local_document_parser_factory: Callable[[], LocalDocumentParser] | None = None,
        parsed_cache_factory: Callable[[Path], ParsedDocumentCache] | None = None,
    ) -> None:
        self._id_factory = id_factory or self._default_id
        self._writer = writer or ResearchResultWriter()
        self._guardrail = guardrail or ResearchResultGuardrail()
        self._stdout = stdout or sys.stdout
        self._parsed_cache_directory_resolver = (
            parsed_cache_directory_resolver or resolve_parsed_document_cache_directory
        )
        self._local_document_parser_factory = (
            local_document_parser_factory or LocalDocumentParser
        )
        self._parsed_cache_factory = parsed_cache_factory or (
            lambda directory: FileParsedDocumentCache(directory=directory)
        )

    def __call__(
        self,
        question: str,
        objective: str,
        sources: tuple[LocalDocumentAccessResult, ...],
        output_dir: Path,
        access_policy: LocalDocumentAccessPolicy,
        external_send_approval: LocalExternalSendApproval | None,
    ) -> int:
        """Run the local pipeline and write report artifacts."""

        execution_id = self._id_factory().strip()

        if not execution_id:
            raise RuntimeError("research execution ID factory returned blank value")

        self._validate_before_document_load(
            sources=sources,
            approval=external_send_approval,
        )
        fresh_sources = self._validate_before_parsed_cache(
            sources=sources,
            access_policy=access_policy,
            approval=external_send_approval,
        )
        bundle = self._load_documents(fresh_sources)
        self._validate_before_pipeline_build(
            sources=fresh_sources,
            access_policy=access_policy,
            approval=external_send_approval,
        )
        pipeline = self._build_pipeline(
            bundle,
            question=question,
            objective=objective,
        )
        request = ResearchRequest(
            request_id=execution_id,
            question=question,
            objective=objective,
            preferred_source_types=[
                ResearchSourceType.OTHER,
            ],
            maximum_sources=max(1, len(sources)),
        )

        result = pipeline.run(
            request,
            workspace_id=f"{execution_id}-workspace",
        )
        self._guardrail.validate(
            result,
            execution_id=execution_id,
        )
        paths = self._writer.write(
            result,
            output_dir=output_dir,
            execution_id=execution_id,
        )

        print(
            f"AIRA report: {paths.report_path}",
            file=self._stdout,
        )
        print(
            f"AIRA result: {paths.result_path}",
            file=self._stdout,
        )

        return 0

    @staticmethod
    def _validate_before_parsed_cache(
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        access_policy: LocalDocumentAccessPolicy,
        approval: LocalExternalSendApproval | None,
    ) -> tuple[LocalDocumentAccessResult, ...]:
        """Freshly validate raw sources before any parsed-cache lookup."""

        access_gate = LocalDocumentAccessGate(access_policy)
        return tuple(access_gate.validate(source.resolved_path) for source in sources)

    def _load_documents(
        self,
        sources: tuple[LocalDocumentAccessResult, ...],
    ) -> LocalDocumentBundle:
        """Compose persistent parsing only after authoritative access checks."""

        cache = self._parsed_cache_factory(self._parsed_cache_directory_resolver())
        parser = CachingLocalDocumentParser(
            parser=self._local_document_parser_factory(),
            cache=cache,
        )
        return LocalDocumentAdapter(parser=parser).load_validated(sources)

    def _validate_before_document_load(
        self,
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        approval: LocalExternalSendApproval | None,
    ) -> None:
        """Leave deterministic Local Research approval-free."""

    def _validate_before_pipeline_build(
        self,
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        access_policy: LocalDocumentAccessPolicy,
        approval: LocalExternalSendApproval | None,
    ) -> None:
        """Leave deterministic Local Research without provider revalidation."""

    def _build_pipeline(
        self,
        bundle: LocalDocumentBundle,
        *,
        question: str,
        objective: str,
    ) -> SingleResearchAgentPipeline:
        """Build the deterministic offline Local pipeline."""

        return build_local_research_pipeline(bundle)

    @staticmethod
    def _default_id() -> str:
        """Return a unique local execution identifier."""

        return f"aira-{uuid4().hex}"


class SemanticLocalResearchHandler(LocalResearchHandler):
    """Execute semantic Local research with bounded model workers."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        writer: ResearchResultWriter | None = None,
        guardrail: ResearchResultGuardrail | None = None,
        stdout: TextIO | None = None,
        settings_loader: (Callable[[], Settings] | None) = None,
        openai_client_factory: (Callable[[Settings], OpenAI] | None) = None,
        local_worker_settings_loader: (Callable[[], LocalWorkerSettings] | None) = None,
        embedding_cache_directory_resolver: (Callable[[], Path] | None) = None,
        parsed_cache_directory_resolver: Callable[[], Path] | None = None,
        local_document_parser_factory: Callable[[], LocalDocumentParser] | None = None,
        parsed_cache_factory: Callable[[Path], ParsedDocumentCache] | None = None,
    ) -> None:
        super().__init__(
            id_factory=id_factory,
            writer=writer,
            guardrail=guardrail,
            stdout=stdout,
            parsed_cache_directory_resolver=parsed_cache_directory_resolver,
            local_document_parser_factory=local_document_parser_factory,
            parsed_cache_factory=parsed_cache_factory,
        )
        self._settings_loader = settings_loader or load_settings
        self._openai_client_factory = openai_client_factory or create_openai_client
        self._local_worker_settings_loader = (
            local_worker_settings_loader or load_local_worker_settings
        )
        self._embedding_cache_directory_resolver = (
            embedding_cache_directory_resolver or resolve_embedding_cache_directory
        )

    def _validate_before_document_load(
        self,
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        approval: LocalExternalSendApproval | None,
    ) -> None:
        LocalExternalSendApprovalGate().validate(approval, sources)

    def _validate_before_pipeline_build(
        self,
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        access_policy: LocalDocumentAccessPolicy,
        approval: LocalExternalSendApproval | None,
    ) -> None:
        access_gate = LocalDocumentAccessGate(access_policy)
        fresh_sources = tuple(
            access_gate.validate(source.resolved_path) for source in sources
        )
        LocalExternalSendApprovalGate().validate(
            approval,
            fresh_sources,
        )

    @staticmethod
    def _validate_before_parsed_cache(
        *,
        sources: tuple[LocalDocumentAccessResult, ...],
        access_policy: LocalDocumentAccessPolicy,
        approval: LocalExternalSendApproval | None,
    ) -> tuple[LocalDocumentAccessResult, ...]:
        """Bind approval to fresh identities before parsed-cache access."""

        fresh_sources = LocalResearchHandler._validate_before_parsed_cache(
            sources=sources,
            access_policy=access_policy,
            approval=approval,
        )
        LocalExternalSendApprovalGate().validate(approval, fresh_sources)
        return fresh_sources

    def _build_pipeline(
        self,
        bundle: LocalDocumentBundle,
        *,
        question: str,
        objective: str,
    ) -> SingleResearchAgentPipeline:
        """Build the semantic Local pipeline after source validation."""

        embedding_cache = FileEmbeddingCache(
            directory=self._embedding_cache_directory_resolver()
        )
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
            claim_relevance_budget=LOCAL_CLAIM_RELEVANCE_BUDGET,
        )
        evidence_extractor = PipelineEvidenceExtractorAdapter(
            SemanticResearchEvidenceExtractor(
                question=question,
                objective=objective,
                paragraph_extractor=ParagraphEvidenceExtractor(),
                shortlister=EmbeddingSemanticEvidenceShortlister(
                    embedding_provider=CachingEmbeddingProvider(
                        provider=OpenAIEmbeddingProvider(
                            client=openai_client,
                        ),
                        cache=embedding_cache,
                    )
                ),
                reranker=SemanticEvidenceReranker(
                    evaluator=OpenAIEvidenceRelevanceEvaluator(
                        client=openai_client,
                        model=settings.openai_model,
                    ),
                    budget=LOCAL_EVIDENCE_RELEVANCE_BUDGET,
                ),
            )
        )
        claim_builder = GenerativePipelineClaimBuilder(
            generator=OpenAIEvidenceClaimGenerator(
                client=openai_client,
                model=settings.openai_model,
            ),
            budget=LOCAL_CLAIM_GENERATION_BUDGET,
        )

        return build_local_research_pipeline(
            bundle,
            evidence_extractor=evidence_extractor,
            claim_builder=claim_builder,
            semantic_citation_verifier=(bounded_workers.semantic_citation_verifier),
            claim_relevance_evaluator=(bounded_workers.claim_relevance_evaluator),
            answer_coverage_evaluator=(bounded_workers.answer_coverage_evaluator),
        )
