"""Offline tests for bounded cross-source evidence reranking runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.exceptions import StructuredResponseParseError
from app.research.bounded_cross_source_evidence_reranker import (
    BoundedCrossSourceEvidenceReranker,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceBatchEvaluationResult,
    EvidenceRelevanceEvaluationResult,
)
from app.schemas.cross_source_evidence_reranking import (
    CrossSourceEvidenceRerankingRequest,
    EvidenceRerankingBudget,
    EvidenceRerankingEvaluationState,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.hybrid_retrieval import (
    HybridRetrievalMatch,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult
from app.services.text_generation import TokenUsage


def _judgment(level: EvidenceRelevanceLevel, score: float):
    return EvidenceRelevanceJudgment(
        relevance_level=level,
        relevance_score=score,
        rationale="Controlled offline test judgment.",
    )


def _match(chunk_id: str, rank: int) -> HybridRetrievalMatch:
    text = f"Evidence {chunk_id}."
    contribution = 1 / (60 + rank)
    return HybridRetrievalMatch(
        retrieval=RetrievalResult(
            chunk=DocumentChunk(
                document_id=f"document-{chunk_id}",
                chunk_id=chunk_id,
                ordinal=rank - 1,
                text=text,
                start_char=0,
                end_char=len(text),
                metadata={"source_id": f"source-{chunk_id}"},
            ),
            score=contribution,
            rank=rank,
        ),
        rrf_k=60,
        keyword_rank=rank,
        keyword_score=1 / rank,
        keyword_contribution=contribution,
        fused_score=contribution,
        matched_channel_count=1,
    )


def _hybrid(*ids: str) -> HybridRetrievalResponse:
    matches = [_match(value, rank) for rank, value in enumerate(ids, 1)]
    return HybridRetrievalResponse(
        request=HybridRetrievalRequest(top_k=max(1, len(matches))),
        keyword_result_count=len(matches),
        semantic_result_count=0,
        unique_chunk_count=len(matches),
        matches=matches,
    )


def _request(
    *,
    maximum_candidates: int = 8,
    attempts: int = 8,
    tokens: int = 1000,
    elapsed: float = 30.0,
) -> CrossSourceEvidenceRerankingRequest:
    return CrossSourceEvidenceRerankingRequest(
        question="Which evidence explains the mechanism?",
        objective="Find direct and partial support.",
        maximum_candidates=maximum_candidates,
        budget=EvidenceRerankingBudget(
            maximum_attempts=attempts,
            maximum_recorded_tokens=tokens,
            maximum_elapsed_seconds=elapsed,
        ),
    )


def _usage(tokens: int, elapsed: float) -> TokenUsage:
    return TokenUsage(
        input_tokens=max(tokens - 1, 0),
        cached_input_tokens=0,
        output_tokens=1 if tokens else 0,
        reasoning_tokens=0,
        total_tokens=tokens,
    )


@dataclass
class ControlledEvaluator:
    judgments: dict[str, tuple[EvidenceRelevanceLevel, float]]
    single_tokens: int = 5
    single_elapsed: float = 0.1
    calls: list[str] = field(default_factory=list)

    def evaluate(self, *, question: str, objective: str, evidence_excerpt: str):
        self.calls.append(evidence_excerpt)
        level, score = self.judgments[evidence_excerpt]
        return EvidenceRelevanceEvaluationResult(
            judgment=_judgment(level, score),
            response_id=f"offline-response-{len(self.calls)}",
            request_id=f"offline-request-{len(self.calls)}",
            usage=_usage(self.single_tokens, self.single_elapsed),
            elapsed_seconds=self.single_elapsed,
        )


@dataclass
class ControlledBatchEvaluator(ControlledEvaluator):
    batch_tokens: int = 20
    batch_elapsed: float = 0.2
    batch_error: Exception | None = None
    omit_last_id: bool = False
    batch_calls: int = 0

    def evaluate_batch(self, *, question: str, objective: str, evidence_items):
        self.batch_calls += 1
        if self.batch_error is not None:
            raise self.batch_error
        selected = evidence_items[:-1] if self.omit_last_id else evidence_items
        return EvidenceRelevanceBatchEvaluationResult(
            judgments={
                item_id: _judgment(*self.judgments[text]) for item_id, text in selected
            },
            response_id="offline-batch-response",
            request_id="offline-batch-request",
            usage=_usage(self.batch_tokens, self.batch_elapsed),
            elapsed_seconds=self.batch_elapsed,
        )


def _map(*pairs):
    return {f"Evidence {name}.": value for name, value in pairs}


def test_empty_hybrid_response_makes_no_evaluator_call() -> None:
    evaluator = ControlledEvaluator({})
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=_hybrid(), request=_request()
    )
    assert result.items == []
    assert result.usage.attempts == 0
    assert evaluator.calls == []


def test_single_evaluator_orders_categories_and_preserves_hybrid() -> None:
    hybrid = _hybrid("partial", "direct", "irrelevant")
    evaluator = ControlledEvaluator(
        _map(
            ("partial", (EvidenceRelevanceLevel.PARTIALLY_RELEVANT, 0.7)),
            ("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)),
            ("irrelevant", (EvidenceRelevanceLevel.IRRELEVANT, 0.1)),
        )
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request()
    )
    assert [item.hybrid_match.retrieval.chunk.chunk_id for item in result.items] == [
        "direct",
        "partial",
        "irrelevant",
    ]
    assert result.evaluated_count == 3
    assert result.unevaluated_count == 0
    assert result.usage.attempts == 3
    assert {item.hybrid_match.retrieval.chunk.chunk_id for item in result.items} == {
        match.retrieval.chunk.chunk_id for match in hybrid.matches
    }


def test_batch_fast_path_uses_one_attempt_and_maps_by_item_id() -> None:
    hybrid = _hybrid("partial", "direct")
    evaluator = ControlledBatchEvaluator(
        _map(
            ("partial", (EvidenceRelevanceLevel.PARTIALLY_RELEVANT, 0.7)),
            ("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)),
        )
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request()
    )
    assert evaluator.batch_calls == 1
    assert evaluator.calls == []
    assert result.usage.attempts == 1
    assert result.usage.recorded_tokens == 20
    assert result.items[0].hybrid_match.retrieval.chunk.chunk_id == "direct"


def test_malformed_batch_mapping_falls_back_and_charges_attempt() -> None:
    hybrid = _hybrid("direct", "partial")
    evaluator = ControlledBatchEvaluator(
        _map(
            ("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)),
            ("partial", (EvidenceRelevanceLevel.PARTIALLY_RELEVANT, 0.6)),
        ),
        omit_last_id=True,
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request()
    )
    assert evaluator.batch_calls == 1
    assert len(evaluator.calls) == 2
    assert result.usage.attempts == 3


def test_structured_batch_failure_with_no_attempt_left_preserves_unevaluated() -> None:
    hybrid = _hybrid("direct")
    evaluator = ControlledBatchEvaluator(
        _map(("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9))),
        batch_error=StructuredResponseParseError("bad batch"),
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request(attempts=1)
    )
    assert result.budget_exhausted is True
    assert result.evaluated_count == 0
    assert result.unevaluated_count == 1
    assert (
        result.items[0].evaluation_state is EvidenceRerankingEvaluationState.UNEVALUATED
    )


def test_single_path_stops_after_successful_token_overrun() -> None:
    hybrid = _hybrid("direct", "remaining")
    evaluator = ControlledEvaluator(
        _map(
            ("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)),
            ("remaining", (EvidenceRelevanceLevel.PARTIALLY_RELEVANT, 0.5)),
        ),
        single_tokens=11,
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request(tokens=10)
    )
    assert result.budget_exhausted is True
    assert result.evaluated_count == 1
    assert result.unevaluated_count == 1
    assert len(evaluator.calls) == 1
    assert result.items[0].judgment is not None


def test_successful_batch_overrun_keeps_all_judgments_and_marks_exhausted() -> None:
    hybrid = _hybrid("direct", "partial")
    evaluator = ControlledBatchEvaluator(
        _map(
            ("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)),
            ("partial", (EvidenceRelevanceLevel.PARTIALLY_RELEVANT, 0.6)),
        ),
        batch_tokens=11,
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request(tokens=10)
    )
    assert result.budget_exhausted is True
    assert result.evaluated_count == 2
    assert result.unevaluated_count == 0


def test_programming_error_is_not_hidden_by_batch_fallback() -> None:
    evaluator = ControlledBatchEvaluator(
        _map(("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9))),
        batch_error=RuntimeError("programming failure"),
    )
    with pytest.raises(RuntimeError, match="programming failure"):
        BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
            hybrid_response=_hybrid("direct"), request=_request()
        )


def test_candidate_bound_is_checked_before_evaluator_call() -> None:
    evaluator = ControlledEvaluator({})
    with pytest.raises(ValueError, match="maximum_candidates"):
        BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
            hybrid_response=_hybrid("one", "two"),
            request=_request(maximum_candidates=1),
        )
    assert evaluator.calls == []


def test_original_chunk_text_metadata_offsets_and_hybrid_rank_are_unchanged() -> None:
    hybrid = _hybrid("direct")
    original = hybrid.matches[0]
    evaluator = ControlledEvaluator(
        _map(("direct", (EvidenceRelevanceLevel.DIRECTLY_RELEVANT, 0.9)))
    )
    result = BoundedCrossSourceEvidenceReranker(evaluator=evaluator).rerank(
        hybrid_response=hybrid, request=_request()
    )
    assert result.items[0].hybrid_match == original
    assert result.items[0].hybrid_match.retrieval.chunk == original.retrieval.chunk
    assert result.items[0].hybrid_match.retrieval.rank == 1


@pytest.mark.parametrize("argument", ["hybrid_response", "request"])
def test_runtime_validates_public_input_types(argument: str) -> None:
    values = {"hybrid_response": _hybrid(), "request": _request()}
    values[argument] = "invalid"
    with pytest.raises(TypeError, match=argument):
        BoundedCrossSourceEvidenceReranker(evaluator=ControlledEvaluator({})).rerank(
            **values
        )
