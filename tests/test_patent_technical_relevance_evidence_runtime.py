"""Tests for patent technical-relevance evidence composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from app.budget import ExecutionBudget
from app.config import Settings
from app.rag.embedding_provider import EmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.research.paragraph_evidence_extractor import ParagraphEvidenceExtractor
from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.research.patent_technical_relevance_evidence_runtime import (
    PATENT_EVIDENCE_RELEVANCE_BUDGET,
    PatentTechnicalRelevanceEvidenceRuntime,
    build_openai_patent_technical_relevance_evidence_runtime,
)
from app.research.pipeline_analysis_adapters import PipelineEvidenceExtractorAdapter
from app.research.semantic_evidence_reranker import SemanticEvidenceReranker
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.epo_ops_abstract import EpoOpsVerifiedPatentRecord
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_research_collection_result import (
    PatentResearchCollectionResult,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    PatentSearchQuery,
    PatentSearchQueryPurpose,
)
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
)
from app.schemas.research_evidence import ResearchEvidenceSet
from app.services.text_generation import TokenUsage


def patent_request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="How can pressure sensors detect seat occupancy?",
        objective="Identify pressure sensors for seat occupancy.",
        maximum_search_results=2,
        maximum_sources=2,
        maximum_bytes=4096,
    )


def verified_record(
    *,
    publication_number: str,
    title: str,
    abstract_text: str,
) -> EpoOpsVerifiedPatentRecord:
    return EpoOpsVerifiedPatentRecord(
        metadata=PatentSourceMetadata(
            source_family=PatentSourceFamily.EPO_OPS,
            publication_number=publication_number,
            title=title,
            source_url=(
                "https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/docdb/{publication_number}/abstract"
            ),
            metadata_verification_state=(PatentMetadataVerificationState.VERIFIED),
            publication_date=date(2025, 1, 15),
        ),
        abstract_text=abstract_text,
        abstract_language="en",
    )


def execution(
    records: tuple[EpoOpsVerifiedPatentRecord, ...],
) -> PatentResearchPlanExecutionResult:
    request = patent_request()
    query = PatentSearchQuery(
        cql_query=(
            'ta all "pressure sensors" and ta all "seat occupancy" and pd < 20260818'
        ),
        purpose=PatentSearchQueryPurpose.PRIMARY,
    )
    bibliographic_records = tuple(
        EpoOpsBibliographicRecord(
            publication_number=record.metadata.publication_number,
            publication_docdb=(
                f"{record.metadata.publication_number[:2]}."
                f"{record.metadata.publication_number[2:-2]}."
                f"{record.metadata.publication_number[-2:]}"
            ),
            title=record.metadata.title,
            publication_date=record.metadata.publication_date,
            source_endpoint=(
                "https://ops.epo.org/3.2/rest-services/"
                "published-data/search/biblio?q=test"
            ),
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=None,
            title_language="en",
        )
        for record in records
    )
    search_request = EpoOpsSearchRequest(
        cql_query=query.cql_query,
        maximum_results=request.maximum_search_results,
    )
    return PatentResearchPlanExecutionResult(
        query=query,
        collection=PatentResearchCollectionResult(
            request=request,
            search_result=EpoOpsBibliographicSearchResult(
                request=search_request,
                records=bibliographic_records,
            ),
            verified_records=records,
        ),
        attempted_queries=(query,),
    )


class ControlledPatentEmbeddingProvider(EmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "controlled-patent-relevance"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=2,
                vector=self._vector(text),
            )
            for text in texts
        ]

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        if "seat occupancy" in normalized or "person is seated" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]


@dataclass
class ControlledPatentRelevanceEvaluator:
    calls: list[str]

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        self.calls.append(evidence_excerpt)
        relevant = "person is seated" in evidence_excerpt.casefold()
        level = (
            EvidenceRelevanceLevel.DIRECTLY_RELEVANT
            if relevant
            else EvidenceRelevanceLevel.IRRELEVANT
        )
        return EvidenceRelevanceEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=level,
                relevance_score=0.95 if relevant else 0.05,
                rationale=(
                    "The passage directly describes seat occupancy detection."
                    if relevant
                    else "The passage concerns a different pressure-sensing use."
                ),
                issues=[],
            ),
            response_id=("resp-direct" if relevant else "resp-irrelevant"),
            request_id="req-controlled",
            usage=TokenUsage(
                input_tokens=10,
                cached_input_tokens=0,
                output_tokens=2,
                reasoning_tokens=0,
                total_tokens=12,
            ),
            elapsed_seconds=0.0,
        )


def evidence_runtime(
    evaluator: ControlledPatentRelevanceEvaluator,
) -> PatentTechnicalRelevanceEvidenceRuntime:
    extractor = PipelineEvidenceExtractorAdapter(
        SemanticResearchEvidenceExtractor(
            question=patent_request().question,
            objective=patent_request().objective,
            paragraph_extractor=ParagraphEvidenceExtractor(
                maximum_evidence=3,
                minimum_characters=40,
            ),
            shortlister=EmbeddingSemanticEvidenceShortlister(
                embedding_provider=ControlledPatentEmbeddingProvider(),
                maximum_candidates=4,
            ),
            reranker=SemanticEvidenceReranker(
                evaluator=evaluator,
                budget=ExecutionBudget(
                    max_attempts=4,
                    max_recorded_tokens=1000,
                    max_elapsed_seconds=10.0,
                ),
            ),
            maximum_evidence=2,
        )
    )
    return PatentTechnicalRelevanceEvidenceRuntime(
        evidence_extractor=extractor,
    )


def test_runtime_reuses_generic_semantic_stack_for_patent_abstracts() -> None:
    relevant = (
        "A seat occupancy system uses pressure sensors to determine whether "
        "a person is seated and automatically updates an occupancy state."
    )
    irrelevant = (
        "An intraocular pressure sensor measures pressure within an eye and "
        "reports ophthalmic measurements for clinical monitoring."
    )
    evaluator = ControlledPatentRelevanceEvaluator(calls=[])

    result = evidence_runtime(evaluator).extract(
        execution(
            (
                verified_record(
                    publication_number="EP123456A1",
                    title="Seat occupancy sensing system",
                    abstract_text=relevant,
                ),
                verified_record(
                    publication_number="EP654321B1",
                    title="Intraocular pressure sensor",
                    abstract_text=irrelevant,
                ),
            )
        ),
        request_id="patent-relevance-001",
    )

    assert len(result.document_set.documents) == 2
    assert len(result.evidence_set.evidence) == 1

    evidence = result.evidence_set.evidence[0]
    document = result.document_set.documents[0]

    assert evidence.excerpt == relevant
    assert evidence.relevance_score == 0.95
    assert evidence.metadata["semantic_relevance_level"] == "directly_relevant"
    assert evidence.metadata["semantic_evaluated"] == "true"
    assert evidence.metadata["semantic_response_id"] == "resp-direct"
    assert evidence.source_id == document.candidate.source_id
    assert evidence.document_id == document.document_id
    assert (
        document.content[evidence.start_character : evidence.end_character]
        == evidence.excerpt
    )
    assert document.candidate.metadata["patent_publication_number"] == "EP123456A1"
    assert len(evaluator.calls) == 2


def test_all_irrelevant_patent_abstracts_return_no_evidence() -> None:
    irrelevant = (
        "An intraocular pressure sensor measures pressure within an eye and "
        "reports ophthalmic measurements for clinical monitoring."
    )
    evaluator = ControlledPatentRelevanceEvaluator(calls=[])

    result = evidence_runtime(evaluator).extract(
        execution(
            (
                verified_record(
                    publication_number="EP654321B1",
                    title="Intraocular pressure sensor",
                    abstract_text=irrelevant,
                ),
            )
        ),
        request_id="patent-relevance-002",
    )

    assert len(result.document_set.documents) == 1
    assert result.evidence_set.evidence == []
    assert evaluator.calls == [irrelevant]


def test_zero_verified_records_produce_empty_evidence_without_evaluator_calls() -> None:
    evaluator = ControlledPatentRelevanceEvaluator(calls=[])

    result = evidence_runtime(evaluator).extract(
        execution(()),
        request_id="patent-relevance-003",
    )

    assert result.document_set.documents == []
    assert result.evidence_set.evidence == []
    assert evaluator.calls == []


class MismatchedEvidenceExtractor:
    def extract(
        self,
        document_set,
    ) -> ResearchEvidenceSet:
        return ResearchEvidenceSet(
            request_id="different-request",
            document_set=document_set.model_copy(
                update={"request_id": "different-request"},
            ),
            evidence=[],
        )


def test_runtime_rejects_evidence_request_binding_mismatch() -> None:
    runtime = PatentTechnicalRelevanceEvidenceRuntime(
        evidence_extractor=MismatchedEvidenceExtractor(),
    )

    with pytest.raises(RuntimeError, match="not bound"):
        runtime.extract(
            execution(()),
            request_id="patent-relevance-004",
        )


def settings() -> Settings:
    return Settings(
        openai_api_key="secret",
        openai_model="test-model",
        openai_timeout_seconds=30.0,
        openai_max_retries=2,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )


def test_production_builder_uses_request_semantics_with_injected_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = ControlledPatentRelevanceEvaluator(calls=[])
    embedding = ControlledPatentEmbeddingProvider()

    monkeypatch.setattr(
        "app.research.patent_technical_relevance_evidence_runtime.load_settings",
        lambda: (_ for _ in ()).throw(AssertionError("must not load settings")),
    )
    monkeypatch.setattr(
        "app.research.patent_technical_relevance_evidence_runtime.create_openai_client",
        lambda _settings: (_ for _ in ()).throw(
            AssertionError("must not create client")
        ),
    )

    runtime = build_openai_patent_technical_relevance_evidence_runtime(
        patent_request(),
        embedding_provider=embedding,
        relevance_evaluator=evaluator,
    )

    result = runtime.extract(
        execution(
            (
                verified_record(
                    publication_number="EP123456A1",
                    title="Seat occupancy sensing system",
                    abstract_text=(
                        "A seat occupancy system uses pressure sensors to determine "
                        "whether a person is seated and automatically updates an "
                        "occupancy state."
                    ),
                ),
            )
        ),
        request_id="patent-production-builder-001",
    )

    assert len(result.evidence_set.evidence) == 1
    assert (
        result.evidence_set.evidence[0].metadata["semantic_relevance_level"]
        == "directly_relevant"
    )
    assert evaluator.calls


def test_production_builder_creates_openai_workers_when_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(),
        embeddings=SimpleNamespace(),
    )
    seen_settings = []
    configured = settings()

    monkeypatch.setattr(
        "app.research.patent_technical_relevance_evidence_runtime.create_openai_client",
        lambda actual_settings: (seen_settings.append(actual_settings), fake_client)[1],
    )

    runtime = build_openai_patent_technical_relevance_evidence_runtime(
        patent_request(),
        settings=configured,
    )

    assert isinstance(runtime, PatentTechnicalRelevanceEvidenceRuntime)
    assert seen_settings == [configured]


def test_production_builder_uses_bounded_default_budget() -> None:
    assert PATENT_EVIDENCE_RELEVANCE_BUDGET.max_attempts == 4
    assert PATENT_EVIDENCE_RELEVANCE_BUDGET.max_recorded_tokens == 8_000
    assert PATENT_EVIDENCE_RELEVANCE_BUDGET.max_elapsed_seconds == 60.0
