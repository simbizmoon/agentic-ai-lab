"""Offline tests for cross-source evidence reranking contracts."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.schemas.cross_source_evidence_reranking import (
    CrossSourceEvidenceRerankingRequest,
    CrossSourceEvidenceRerankingResult,
    CrossSourceEvidenceRerankItem,
    EvidenceRerankingBudget,
    EvidenceRerankingEvaluationState,
    EvidenceRerankingUsage,
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


def _budget() -> EvidenceRerankingBudget:
    return EvidenceRerankingBudget(
        maximum_attempts=2,
        maximum_recorded_tokens=1000,
        maximum_elapsed_seconds=30.0,
    )


def _request(maximum_candidates: int = 8) -> CrossSourceEvidenceRerankingRequest:
    return CrossSourceEvidenceRerankingRequest(
        question="How does the mechanism work?",
        objective="Identify directly supporting evidence.",
        maximum_candidates=maximum_candidates,
        budget=_budget(),
    )


def _hybrid_match(chunk_id: str, rank: int) -> HybridRetrievalMatch:
    text = f"Exact evidence for {chunk_id}."
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
        keyword_score=1.0 / rank,
        keyword_contribution=contribution,
        fused_score=contribution,
        matched_channel_count=1,
    )


def _hybrid(*ids: str) -> HybridRetrievalResponse:
    matches = [_hybrid_match(value, rank) for rank, value in enumerate(ids, 1)]
    return HybridRetrievalResponse(
        request=HybridRetrievalRequest(top_k=max(len(matches), 1)),
        keyword_result_count=len(matches),
        semantic_result_count=0,
        unique_chunk_count=len(matches),
        matches=matches,
    )


def _judgment(
    level: EvidenceRelevanceLevel,
    score: float,
) -> EvidenceRelevanceJudgment:
    return EvidenceRelevanceJudgment(
        relevance_level=level,
        relevance_score=score,
        rationale=f"Offline controlled {level.value} judgment.",
    )


def _evaluated(
    match: HybridRetrievalMatch,
    *,
    final_rank: int,
    level: EvidenceRelevanceLevel,
    score: float,
) -> CrossSourceEvidenceRerankItem:
    return CrossSourceEvidenceRerankItem(
        hybrid_match=match,
        evaluation_state=EvidenceRerankingEvaluationState.EVALUATED,
        judgment=_judgment(level, score),
        response_id="offline-test-response",
        request_id="offline-test-request",
        final_rank=final_rank,
    )


def _unevaluated(
    match: HybridRetrievalMatch,
    final_rank: int,
) -> CrossSourceEvidenceRerankItem:
    return CrossSourceEvidenceRerankItem(
        hybrid_match=match,
        evaluation_state=EvidenceRerankingEvaluationState.UNEVALUATED,
        final_rank=final_rank,
    )


def test_budget_and_request_accept_bounded_values() -> None:
    request = _request()
    assert request.maximum_candidates == 8
    assert request.budget.maximum_attempts == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_attempts", 0),
        ("maximum_recorded_tokens", 0),
        ("maximum_elapsed_seconds", 0.0),
        ("maximum_elapsed_seconds", math.inf),
    ],
)
def test_budget_rejects_invalid_bounds(field: str, value: object) -> None:
    data = _budget().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        EvidenceRerankingBudget(**data)


@pytest.mark.parametrize("field", ["question", "objective"])
def test_request_rejects_blank_text(field: str) -> None:
    data = _request().model_dump()
    data[field] = "  "
    with pytest.raises(ValidationError, match="must not be blank"):
        CrossSourceEvidenceRerankingRequest(**data)


def test_evaluated_item_requires_judgment_and_response_identity() -> None:
    data = _evaluated(
        _hybrid_match("chunk-a", 1),
        final_rank=1,
        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        score=0.9,
    ).model_dump()
    data["judgment"] = None
    with pytest.raises(ValidationError, match="requires a judgment"):
        CrossSourceEvidenceRerankItem(**data)
    data = _evaluated(
        _hybrid_match("chunk-a", 1),
        final_rank=1,
        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        score=0.9,
    ).model_dump()
    data["response_id"] = " "
    with pytest.raises(ValidationError, match="requires response_id"):
        CrossSourceEvidenceRerankItem(**data)


def test_unevaluated_item_forbids_judgment_and_provider_identity() -> None:
    data = _unevaluated(_hybrid_match("chunk-a", 1), 1).model_dump()
    data["judgment"] = _judgment(EvidenceRelevanceLevel.IRRELEVANT, 0.1)
    with pytest.raises(ValidationError, match="must not contain a judgment"):
        CrossSourceEvidenceRerankItem(**data)
    data = _unevaluated(_hybrid_match("chunk-a", 1), 1).model_dump()
    data["response_id"] = "invented"
    with pytest.raises(ValidationError, match="provider identity"):
        CrossSourceEvidenceRerankItem(**data)


def test_result_accepts_category_order_and_preserves_hybrid_matches() -> None:
    hybrid = _hybrid("partial", "direct", "unknown", "irrelevant")
    items = [
        _evaluated(
            hybrid.matches[1],
            final_rank=1,
            level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            score=0.9,
        ),
        _evaluated(
            hybrid.matches[0],
            final_rank=2,
            level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            score=0.7,
        ),
        _unevaluated(hybrid.matches[2], 3),
        _evaluated(
            hybrid.matches[3],
            final_rank=4,
            level=EvidenceRelevanceLevel.IRRELEVANT,
            score=0.1,
        ),
    ]
    result = CrossSourceEvidenceRerankingResult(
        request=_request(),
        hybrid_response=hybrid,
        items=items,
        usage=EvidenceRerankingUsage(
            attempts=1, recorded_tokens=20, elapsed_seconds=0.1
        ),
        budget_exhausted=True,
        candidate_count=4,
        evaluated_count=3,
        unevaluated_count=1,
    )
    assert result.items[0].hybrid_match is hybrid.matches[1]
    assert result.items[2].judgment is None


def test_empty_hybrid_result_has_empty_reranking_result() -> None:
    result = CrossSourceEvidenceRerankingResult(
        request=_request(),
        hybrid_response=_hybrid(),
        items=[],
        candidate_count=0,
        evaluated_count=0,
        unevaluated_count=0,
    )
    assert result.items == []


def test_candidate_count_must_match_hybrid_and_maximum() -> None:
    hybrid = _hybrid("chunk-a", "chunk-b")
    with pytest.raises(ValidationError, match="must match hybrid"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            candidate_count=1,
            evaluated_count=0,
            unevaluated_count=0,
        )
    with pytest.raises(ValidationError, match="maximum_candidates"):
        CrossSourceEvidenceRerankingResult(
            request=_request(maximum_candidates=1),
            hybrid_response=hybrid,
            candidate_count=2,
            evaluated_count=0,
            unevaluated_count=0,
        )


def test_items_must_cover_exact_candidate_set() -> None:
    hybrid = _hybrid("chunk-a")
    with pytest.raises(ValidationError, match="cover every"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=[],
            candidate_count=1,
            evaluated_count=0,
            unevaluated_count=1,
            budget_exhausted=True,
        )


def test_item_cannot_replace_exact_hybrid_match() -> None:
    hybrid = _hybrid("chunk-a")
    replacement = _hybrid_match("chunk-a", 1).model_copy(update={"keyword_score": 0.5})
    with pytest.raises(ValidationError, match="preserve exact hybrid match"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=[
                _evaluated(
                    replacement,
                    final_rank=1,
                    level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                    score=0.9,
                )
            ],
            candidate_count=1,
            evaluated_count=1,
            unevaluated_count=0,
        )


def test_counts_must_match_item_states() -> None:
    hybrid = _hybrid("chunk-a")
    item = _evaluated(
        hybrid.matches[0],
        final_rank=1,
        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        score=0.9,
    )
    with pytest.raises(ValidationError, match="evaluated_count"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=[item],
            candidate_count=1,
            evaluated_count=0,
            unevaluated_count=1,
        )


def test_final_positions_must_be_contiguous() -> None:
    hybrid = _hybrid("chunk-a")
    item = _evaluated(
        hybrid.matches[0],
        final_rank=2,
        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        score=0.9,
    )
    with pytest.raises(ValidationError, match="contiguous"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=[item],
            candidate_count=1,
            evaluated_count=1,
            unevaluated_count=0,
        )


def test_result_rejects_wrong_relevance_order() -> None:
    hybrid = _hybrid("partial", "direct")
    items = [
        _evaluated(
            hybrid.matches[0],
            final_rank=1,
            level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            score=0.8,
        ),
        _evaluated(
            hybrid.matches[1],
            final_rank=2,
            level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            score=0.7,
        ),
    ]
    with pytest.raises(ValidationError, match="relevance ordering"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=items,
            candidate_count=2,
            evaluated_count=2,
            unevaluated_count=0,
        )


def test_same_category_uses_score_then_original_hybrid_rank() -> None:
    hybrid = _hybrid("lower", "higher")
    correctly_ordered = [
        _evaluated(
            hybrid.matches[1],
            final_rank=1,
            level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            score=0.9,
        ),
        _evaluated(
            hybrid.matches[0],
            final_rank=2,
            level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            score=0.8,
        ),
    ]
    result = CrossSourceEvidenceRerankingResult(
        request=_request(),
        hybrid_response=hybrid,
        items=correctly_ordered,
        candidate_count=2,
        evaluated_count=2,
        unevaluated_count=0,
    )
    assert result.items[0].judgment.relevance_score == 0.9  # type: ignore[union-attr]


def test_unevaluated_candidates_require_budget_exhaustion() -> None:
    hybrid = _hybrid("chunk-a")
    with pytest.raises(ValidationError, match="require budget_exhausted"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=hybrid,
            items=[_unevaluated(hybrid.matches[0], 1)],
            candidate_count=1,
            evaluated_count=0,
            unevaluated_count=1,
            budget_exhausted=False,
        )


def test_over_budget_usage_requires_exhausted_marker() -> None:
    with pytest.raises(ValidationError, match="over-budget usage"):
        CrossSourceEvidenceRerankingResult(
            request=_request(),
            hybrid_response=_hybrid(),
            usage=EvidenceRerankingUsage(
                attempts=3,
                recorded_tokens=0,
                elapsed_seconds=0.0,
            ),
            candidate_count=0,
            evaluated_count=0,
            unevaluated_count=0,
        )


def test_models_are_frozen_and_forbid_unknown_fields() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        request.maximum_candidates = 2
    with pytest.raises(ValidationError):
        EvidenceRerankingUsage(unknown=True)
