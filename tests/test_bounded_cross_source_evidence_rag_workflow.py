"""Offline integration tests for reranked cross-source RAG context."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.research.bounded_cross_source_evidence_rag_workflow import (
    BoundedCrossSourceEvidenceRagWorkflow,
)
from app.research.bounded_cross_source_evidence_reranker import (
    BoundedCrossSourceEvidenceReranker,
)
from app.research.bounded_hybrid_retrieval_workflow import (
    BoundedHybridRetrievalWorkflow,
)
from app.research.deterministic_rag_context_packer import (
    DeterministicRagContextPacker,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.schemas.cross_source_evidence_rag_workflow import (
    CrossSourceEvidenceRagWorkflowRequest,
    CrossSourceEvidenceRagWorkflowResult,
)
from app.schemas.cross_source_evidence_reranking import (
    CrossSourceEvidenceRerankingRequest,
    EvidenceRerankingBudget,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import TextEmbedding
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.hybrid_retrieval import HybridRetrievalRequest
from app.schemas.hybrid_retrieval_workflow import HybridRetrievalWorkflowRequest
from app.schemas.keyword_retrieval import KeywordRetrievalRequest
from app.schemas.rag_context_packing import (
    RagContextOmissionReason,
    RagContextPackingBudget,
)
from app.schemas.retrieval_result import RetrievalResult
from app.services.text_generation import TokenUsage


def _chunk(name: str, text: str, source_type: str) -> DocumentChunk:
    return DocumentChunk(
        document_id=f"document-{name}",
        chunk_id=f"chunk-{name}",
        ordinal=0,
        text=text,
        start_char=0,
        end_char=len(text),
        metadata={"source_id": f"source-{name}", "source_type": source_type},
    )


PATENT = _chunk(
    "patent",
    "A patent frame includes stop members engaging a mould container.",
    "patent",
)
ACADEMIC = _chunk(
    "academic",
    "An academic study explains grounded retrieval augmented generation.",
    "academic",
)
OFFICIAL = _chunk(
    "official",
    "Official guidance discusses unrelated account administration.",
    "official_documentation",
)


@dataclass
class SemanticStub:
    results: list[RetrievalResult]

    def search(self, *, query_embedding: TextEmbedding, top_k: int):
        del query_embedding
        return self.results[:top_k]


@dataclass
class ControlledEvaluator:
    levels: dict[str, EvidenceRelevanceLevel]
    calls: list[str] = field(default_factory=list)

    def evaluate(self, *, question: str, objective: str, evidence_excerpt: str):
        del question, objective
        self.calls.append(evidence_excerpt)
        level = self.levels[evidence_excerpt]
        score = {
            EvidenceRelevanceLevel.DIRECTLY_RELEVANT: 0.9,
            EvidenceRelevanceLevel.PARTIALLY_RELEVANT: 0.6,
            EvidenceRelevanceLevel.IRRELEVANT: 0.1,
        }[level]
        return EvidenceRelevanceEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=level,
                relevance_score=score,
                rationale=f"Controlled {level.value} judgment.",
                issues=[]
                if level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
                else ["fixture"],
            ),
            response_id=f"response-{len(self.calls)}",
            request_id=f"request-{len(self.calls)}",
            usage=TokenUsage(
                input_tokens=2,
                cached_input_tokens=0,
                output_tokens=1,
                reasoning_tokens=0,
                total_tokens=3,
            ),
            elapsed_seconds=0.01,
        )


def _request(
    *,
    attempts: int = 3,
    packing_budget: RagContextPackingBudget | None = None,
) -> CrossSourceEvidenceRagWorkflowRequest:
    return CrossSourceEvidenceRagWorkflowRequest(
        retrieval=HybridRetrievalWorkflowRequest(
            keyword_request=KeywordRetrievalRequest(
                query="patent frame grounded retrieval",
                top_k=3,
            ),
            query_embedding=TextEmbedding(
                vector=[1.0, 0.0],
                dimensions=2,
                model_name="offline-test",
            ),
            semantic_top_k=3,
            fusion_request=HybridRetrievalRequest(top_k=3),
        ),
        reranking=CrossSourceEvidenceRerankingRequest(
            question="Which evidence explains the claimed grounded system?",
            objective="Select technically relevant evidence.",
            maximum_candidates=3,
            budget=EvidenceRerankingBudget(
                maximum_attempts=attempts,
                maximum_recorded_tokens=100,
                maximum_elapsed_seconds=10.0,
            ),
        ),
        context_packing_budget=packing_budget,
    )


def _workflow(
    evaluator: ControlledEvaluator,
    *,
    context_packer: DeterministicRagContextPacker | None = None,
):
    semantic = SemanticStub(
        results=[
            RetrievalResult(chunk=ACADEMIC, score=0.95, rank=1),
            RetrievalResult(chunk=OFFICIAL, score=0.50, rank=2),
            RetrievalResult(chunk=PATENT, score=0.40, rank=3),
        ]
    )
    retrieval = BoundedHybridRetrievalWorkflow(semantic_retriever=semantic)  # type: ignore[arg-type]
    return BoundedCrossSourceEvidenceRagWorkflow(
        retrieval_workflow=retrieval,
        reranker=BoundedCrossSourceEvidenceReranker(evaluator=evaluator),
        context_packer=context_packer,
    )


@dataclass(frozen=True)
class WordEstimator:
    estimator_id: str = "stage6-step7-word-estimate-test-v1"

    def estimate_tokens(self, text: str) -> int:
        return len(text.split())


def _packing_budget(*, maximum_items: int = 2) -> RagContextPackingBudget:
    return RagContextPackingBudget(
        maximum_items=maximum_items,
        maximum_utf8_bytes=10_000,
        maximum_estimated_tokens=10_000,
        token_estimator_id=WordEstimator().estimator_id,
    )


def test_hybrid_reranking_builds_context_in_relevance_order() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(evaluator).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL], request=_request()
    )
    assert [item.chunk.chunk_id for item in result.context_retrievals] == [
        PATENT.chunk_id,
        ACADEMIC.chunk_id,
    ]
    assert [item.rank for item in result.context_retrievals] == [1, 2]
    assert [item.score for item in result.context_retrievals] == [0.9, 0.6]
    assert OFFICIAL.text not in result.context.context_text
    assert result.excluded_irrelevant_count == 1
    assert result.excluded_unevaluated_count == 0


def test_context_citations_preserve_exact_cross_source_provenance() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(evaluator).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL], request=_request()
    )
    originals = {chunk.chunk_id: chunk for chunk in [PATENT, ACADEMIC, OFFICIAL]}
    for citation in result.context.citations:
        original = originals[citation.chunk_id]
        assert citation.document_id == original.document_id
        assert (citation.start_char, citation.end_char) == (
            original.start_char,
            original.end_char,
        )
        assert original.metadata["source_id"] in {
            item.hybrid_match.retrieval.chunk.metadata["source_id"]
            for item in result.reranking.items
            if item.hybrid_match.retrieval.chunk.chunk_id == citation.chunk_id
        }


def test_budget_exhaustion_preserves_but_excludes_unevaluated_candidates() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(evaluator).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL], request=_request(attempts=1)
    )
    assert result.reranking.candidate_count == 3
    assert result.reranking.evaluated_count == 1
    assert result.reranking.unevaluated_count == 2
    assert result.excluded_unevaluated_count == 2
    assert len(result.context_retrievals) in {0, 1}
    assert len(result.context.citations) == len(result.context_retrievals)


def test_result_rejects_context_provenance_drift() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(evaluator).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL], request=_request()
    )
    values = result.model_dump(mode="python")
    values["context_retrievals"][0]["chunk"]["document_id"] = "drifted-document"
    try:
        CrossSourceEvidenceRagWorkflowResult.model_validate(values)
    except ValueError as error:
        assert "exact chunk" in str(error) or "citation" in str(error)
    else:
        raise AssertionError("provenance drift must be rejected")


def test_workflow_makes_no_provider_choice_or_quality_judgment() -> None:
    fields = CrossSourceEvidenceRagWorkflowResult.model_fields
    forbidden = {
        "winner",
        "best_source",
        "source_authority",
        "paper_quality",
        "patent_quality",
        "legal_conclusion",
    }
    assert forbidden.isdisjoint(fields)


def test_bounded_packing_limits_final_context_but_preserves_audit_result() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    packer = DeterministicRagContextPacker(token_estimator=WordEstimator())
    result = _workflow(evaluator, context_packer=packer).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL],
        request=_request(packing_budget=_packing_budget(maximum_items=1)),
    )
    assert result.packing is not None
    assert result.packing.usage.candidate_count == 2
    assert result.packing.usage.included_count == 1
    assert result.packing.usage.omitted_count == 1
    assert result.packing.omitted[0].reasons == [RagContextOmissionReason.ITEM_LIMIT]
    assert len(result.reranking.items) == 3
    assert [item.chunk.chunk_id for item in result.context_retrievals] == [
        PATENT.chunk_id
    ]
    assert PATENT.text in result.context.context_text
    assert ACADEMIC.text not in result.context.context_text


def test_packed_context_citation_matches_included_whole_chunk() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(
        evaluator,
        context_packer=DeterministicRagContextPacker(token_estimator=WordEstimator()),
    ).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL],
        request=_request(packing_budget=_packing_budget(maximum_items=1)),
    )
    assert result.packing is not None
    included = result.packing.included[0].retrieval.chunk
    citation = result.context.citations[0]
    assert citation.chunk_id == included.chunk_id
    assert citation.document_id == included.document_id
    assert (citation.start_char, citation.end_char) == (
        included.start_char,
        included.end_char,
    )
    assert included.text in result.context.context_text


def test_packing_budget_requires_runtime_packer() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    with pytest.raises(ValueError, match="context_packer is required"):
        _workflow(evaluator).run(
            chunks=[PATENT, ACADEMIC, OFFICIAL],
            request=_request(packing_budget=_packing_budget()),
        )


def test_legacy_unbounded_request_remains_compatible() -> None:
    evaluator = ControlledEvaluator(
        {
            PATENT.text: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            ACADEMIC.text: EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            OFFICIAL.text: EvidenceRelevanceLevel.IRRELEVANT,
        }
    )
    result = _workflow(evaluator).run(
        chunks=[PATENT, ACADEMIC, OFFICIAL], request=_request()
    )
    assert result.request.context_packing_budget is None
    assert result.packing is None
    assert len(result.context_retrievals) == 2
