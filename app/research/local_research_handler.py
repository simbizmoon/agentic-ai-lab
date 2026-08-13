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
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.hybrid_runtime import (
    build_hybrid_bounded_research_workers,
    legacy_compatible_role_policy,
)
from app.research.local_document_adapter import (
    LocalDocumentAdapter,
    LocalDocumentBundle,
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


class LocalResearchHandler:
    """Execute local research and persist its results."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        writer: ResearchResultWriter | None = None,
        guardrail: ResearchResultGuardrail | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._id_factory = id_factory or self._default_id
        self._writer = writer or ResearchResultWriter()
        self._guardrail = (
            guardrail or ResearchResultGuardrail()
        )
        self._stdout = stdout or sys.stdout

    def __call__(
        self,
        question: str,
        objective: str,
        sources: tuple[Path, ...],
        output_dir: Path,
    ) -> int:
        """Run the local pipeline and write report artifacts."""

        execution_id = self._id_factory().strip()

        if not execution_id:
            raise RuntimeError(
                "research execution ID factory returned blank value"
            )

        bundle = LocalDocumentAdapter().load(sources)
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
        settings_loader: (
            Callable[[], Settings] | None
        ) = None,
        openai_client_factory: (
            Callable[[Settings], OpenAI] | None
        ) = None,
        local_worker_settings_loader: (
            Callable[[], LocalWorkerSettings] | None
        ) = None,
    ) -> None:
        super().__init__(
            id_factory=id_factory,
            writer=writer,
            guardrail=guardrail,
            stdout=stdout,
        )
        self._settings_loader = settings_loader or load_settings
        self._openai_client_factory = (
            openai_client_factory or create_openai_client
        )
        self._local_worker_settings_loader = (
            local_worker_settings_loader
            or load_local_worker_settings
        )

    def _build_pipeline(
        self,
        bundle: LocalDocumentBundle,
        *,
        question: str,
        objective: str,
    ) -> SingleResearchAgentPipeline:
        """Build the semantic Local pipeline after source validation."""

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
                    embedding_provider=OpenAIEmbeddingProvider(
                        client=openai_client,
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
            semantic_citation_verifier=(
                bounded_workers.semantic_citation_verifier
            ),
            claim_relevance_evaluator=(
                bounded_workers.claim_relevance_evaluator
            ),
            answer_coverage_evaluator=(
                bounded_workers.answer_coverage_evaluator
            ),
        )
