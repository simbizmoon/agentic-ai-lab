"""Technical-relevance evidence composition for verified patent records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.budget import ExecutionBudget
from app.config import Settings, load_settings
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.openai_embedding_provider import OpenAIEmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.openai_evidence_relevance_evaluator import (
    OpenAIEvidenceRelevanceEvaluator,
)
from app.research.paragraph_evidence_extractor import ParagraphEvidenceExtractor
from app.research.patent_research_document_adapter import (
    PatentResearchDocumentAdapter,
)
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.research.pipeline_analysis_adapters import PipelineEvidenceExtractorAdapter
from app.research.semantic_evidence_reranker import (
    EvidenceRelevanceEvaluatorProtocol,
    SemanticEvidenceReranker,
)
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_source_document import ResearchSourceDocumentSet
from app.services.openai_client import create_openai_client


class PatentEvidenceExtractorProtocol(Protocol):
    """Minimal document-set evidence extraction contract."""

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        """Return traceable evidence for the supplied patent documents."""


@dataclass(frozen=True)
class PatentTechnicalRelevanceEvidenceResult:
    """One patent execution adapted into traceable technical evidence."""

    execution: PatentResearchPlanExecutionResult
    document_set: ResearchSourceDocumentSet
    evidence_set: ResearchEvidenceSet


class PatentTechnicalRelevanceEvidenceRuntime:
    """Adapt verified patent records and run the generic evidence stack."""

    def __init__(
        self,
        *,
        evidence_extractor: PatentEvidenceExtractorProtocol,
        document_adapter: PatentResearchDocumentAdapter | None = None,
    ) -> None:
        self._evidence_extractor = evidence_extractor
        self._document_adapter = document_adapter or PatentResearchDocumentAdapter()

    def extract(
        self,
        execution: PatentResearchPlanExecutionResult,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> PatentTechnicalRelevanceEvidenceResult:
        """Return request-bound evidence from verified patent abstracts."""

        document_set = self._document_adapter.adapt(
            execution,
            request_id=request_id,
            task_id=task_id,
        )
        evidence_set = self._evidence_extractor.extract(document_set)

        if evidence_set.request_id != document_set.request_id:
            raise RuntimeError(
                "patent evidence set was not bound to the adapted document request"
            )
        if evidence_set.document_set != document_set:
            raise RuntimeError(
                "patent evidence set did not preserve the adapted document set"
            )

        return PatentTechnicalRelevanceEvidenceResult(
            execution=execution,
            document_set=document_set,
            evidence_set=evidence_set,
        )


PATENT_EVIDENCE_RELEVANCE_BUDGET = ExecutionBudget(
    max_attempts=4,
    max_recorded_tokens=8_000,
    max_elapsed_seconds=60.0,
)


def build_openai_patent_technical_relevance_evidence_runtime(
    request: PatentResearchRequest,
    *,
    settings: Settings | None = None,
    openai_client: OpenAI | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    relevance_evaluator: EvidenceRelevanceEvaluatorProtocol | None = None,
    budget: ExecutionBudget | None = None,
) -> PatentTechnicalRelevanceEvidenceRuntime:
    resolved_client = openai_client
    resolved_settings = settings

    if embedding_provider is None or relevance_evaluator is None:
        resolved_settings = resolved_settings or load_settings()
        resolved_client = resolved_client or create_openai_client(resolved_settings)

    resolved_embedding_provider = (
        embedding_provider
        if embedding_provider is not None
        else OpenAIEmbeddingProvider(client=resolved_client)
    )
    resolved_relevance_evaluator = (
        relevance_evaluator
        if relevance_evaluator is not None
        else OpenAIEvidenceRelevanceEvaluator(
            client=resolved_client,
            model=resolved_settings.openai_model,
        )
    )

    evidence_extractor = PipelineEvidenceExtractorAdapter(
        SemanticResearchEvidenceExtractor(
            question=request.question,
            objective=request.objective,
            paragraph_extractor=ParagraphEvidenceExtractor(
                maximum_evidence=4,
                minimum_characters=40,
            ),
            shortlister=EmbeddingSemanticEvidenceShortlister(
                embedding_provider=resolved_embedding_provider,
                maximum_candidates=4,
            ),
            reranker=SemanticEvidenceReranker(
                evaluator=resolved_relevance_evaluator,
                budget=budget or PATENT_EVIDENCE_RELEVANCE_BUDGET,
            ),
            maximum_evidence=2,
        )
    )

    return PatentTechnicalRelevanceEvidenceRuntime(
        evidence_extractor=evidence_extractor,
    )
