"""Offline tests for deterministic hybrid retrieval contracts."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.hybrid_retrieval import (
    HybridRetrievalMatch,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult


def _chunk(chunk_id: str) -> DocumentChunk:
    text = f"Exact evidence for {chunk_id}."
    return DocumentChunk(
        document_id=f"document-{chunk_id}",
        chunk_id=chunk_id,
        ordinal=0,
        text=text,
        start_char=0,
        end_char=len(text),
        metadata={"source_id": f"source-{chunk_id}"},
    )


def _match(
    chunk_id: str = "chunk-a",
    *,
    output_rank: int = 1,
    rrf_k: int = 60,
    keyword_rank: int | None = 1,
    keyword_score: float | None = 1.0,
    semantic_rank: int | None = 2,
    semantic_score: float | None = 0.8,
) -> HybridRetrievalMatch:
    keyword_contribution = (
        None if keyword_rank is None else 1.0 / (rrf_k + keyword_rank)
    )
    semantic_contribution = (
        None if semantic_rank is None else 1.0 / (rrf_k + semantic_rank)
    )
    fused_score = sum(
        value
        for value in (keyword_contribution, semantic_contribution)
        if value is not None
    )
    return HybridRetrievalMatch(
        retrieval=RetrievalResult(
            chunk=_chunk(chunk_id),
            score=fused_score,
            rank=output_rank,
        ),
        rrf_k=rrf_k,
        keyword_rank=keyword_rank,
        keyword_score=keyword_score,
        keyword_contribution=keyword_contribution,
        semantic_rank=semantic_rank,
        semantic_score=semantic_score,
        semantic_contribution=semantic_contribution,
        fused_score=fused_score,
        matched_channel_count=int(keyword_rank is not None)
        + int(semantic_rank is not None),
    )


def test_request_defaults_to_bounded_equal_weight_rrf() -> None:
    request = HybridRetrievalRequest()
    assert request.top_k == 5
    assert request.rrf_k == 60


@pytest.mark.parametrize(
    ("field", "value"),
    [("top_k", 0), ("top_k", 101), ("rrf_k", 0), ("rrf_k", 1001)],
)
def test_request_rejects_out_of_bounds(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        HybridRetrievalRequest(**{field: value})


def test_two_channel_match_preserves_raw_signals_and_rrf_math() -> None:
    match = _match()
    assert match.keyword_rank == 1
    assert match.keyword_score == 1.0
    assert match.semantic_rank == 2
    assert match.semantic_score == 0.8
    assert match.keyword_contribution == pytest.approx(1 / 61)
    assert match.semantic_contribution == pytest.approx(1 / 62)
    assert match.fused_score == pytest.approx((1 / 61) + (1 / 62))
    assert match.retrieval.score == match.fused_score
    assert match.matched_channel_count == 2


def test_keyword_only_match_is_explicit() -> None:
    match = _match(
        semantic_rank=None,
        semantic_score=None,
    )
    assert match.keyword_contribution == pytest.approx(1 / 61)
    assert match.semantic_rank is None
    assert match.semantic_score is None
    assert match.semantic_contribution is None
    assert match.matched_channel_count == 1


def test_semantic_only_match_accepts_negative_raw_cosine_score() -> None:
    match = _match(
        keyword_rank=None,
        keyword_score=None,
        semantic_rank=3,
        semantic_score=-0.25,
    )
    assert match.keyword_rank is None
    assert match.semantic_score == -0.25
    assert match.fused_score == pytest.approx(1 / 63)
    assert match.matched_channel_count == 1


@pytest.mark.parametrize("channel", ["keyword", "semantic"])
def test_channel_fields_must_be_present_together(channel: str) -> None:
    data = _match().model_dump()
    data[f"{channel}_score"] = None
    with pytest.raises(ValidationError, match="must be present together"):
        HybridRetrievalMatch(**data)


@pytest.mark.parametrize("channel", ["keyword", "semantic"])
def test_contribution_must_match_rank_and_rrf_k(channel: str) -> None:
    data = _match().model_dump()
    data[f"{channel}_contribution"] = 0.1
    with pytest.raises(ValidationError, match="reciprocal rank contribution"):
        HybridRetrievalMatch(**data)


def test_match_rejects_wrong_fused_score() -> None:
    data = _match().model_dump()
    data["fused_score"] += 0.01
    data["retrieval"]["score"] = data["fused_score"]
    with pytest.raises(ValidationError, match="channel contributions"):
        HybridRetrievalMatch(**data)


def test_match_rejects_retrieval_score_different_from_fusion() -> None:
    data = _match().model_dump()
    data["retrieval"]["score"] += 0.01
    with pytest.raises(ValidationError, match="retrieval score"):
        HybridRetrievalMatch(**data)


def test_match_rejects_wrong_channel_count() -> None:
    data = _match().model_dump()
    data["matched_channel_count"] = 1
    with pytest.raises(ValidationError, match="present retrieval channels"):
        HybridRetrievalMatch(**data)


@pytest.mark.parametrize("field", ["fused_score", "keyword_score", "semantic_score"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_match_rejects_nonfinite_numeric_values(field: str, value: float) -> None:
    data = _match().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        HybridRetrievalMatch(**data)


def test_response_accepts_ordered_unique_matches() -> None:
    first = _match("chunk-a", output_rank=1)
    second = _match(
        "chunk-b",
        output_rank=2,
        keyword_rank=2,
        keyword_score=0.5,
        semantic_rank=None,
        semantic_score=None,
    )
    response = HybridRetrievalResponse(
        request=HybridRetrievalRequest(top_k=2),
        keyword_result_count=2,
        semantic_result_count=1,
        unique_chunk_count=2,
        matches=[first, second],
    )
    assert response.matches == [first, second]


def test_empty_response_is_valid_for_empty_channels() -> None:
    response = HybridRetrievalResponse(
        request=HybridRetrievalRequest(),
        keyword_result_count=0,
        semantic_result_count=0,
        unique_chunk_count=0,
    )
    assert response.matches == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unique_chunk_count", 3, "must not exceed"),
        ("unique_chunk_count", 0, "must cover"),
    ],
)
def test_response_validates_union_counts(
    field: str,
    value: int,
    message: str,
) -> None:
    data = {
        "request": HybridRetrievalRequest(),
        "keyword_result_count": 1,
        "semantic_result_count": 1,
        "unique_chunk_count": 1,
        "matches": [],
    }
    data[field] = value
    with pytest.raises(ValidationError, match=message):
        HybridRetrievalResponse(**data)


def test_response_rejects_more_matches_than_top_k() -> None:
    with pytest.raises(ValidationError, match="request top_k"):
        HybridRetrievalResponse(
            request=HybridRetrievalRequest(top_k=1),
            keyword_result_count=2,
            semantic_result_count=2,
            unique_chunk_count=2,
            matches=[
                _match("chunk-a", output_rank=1),
                _match("chunk-b", output_rank=2),
            ],
        )


def test_response_rejects_duplicate_chunk_ids_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="chunk IDs must be unique"):
        HybridRetrievalResponse(
            request=HybridRetrievalRequest(top_k=2),
            keyword_result_count=2,
            semantic_result_count=2,
            unique_chunk_count=2,
            matches=[
                _match("chunk-a", output_rank=1),
                _match("CHUNK-A", output_rank=2),
            ],
        )


def test_response_requires_contiguous_final_ranks() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        HybridRetrievalResponse(
            request=HybridRetrievalRequest(),
            keyword_result_count=1,
            semantic_result_count=1,
            unique_chunk_count=1,
            matches=[_match(output_rank=2)],
        )


def test_response_requires_match_and_request_rrf_k_to_agree() -> None:
    with pytest.raises(ValidationError, match="match rrf_k"):
        HybridRetrievalResponse(
            request=HybridRetrievalRequest(rrf_k=10),
            keyword_result_count=1,
            semantic_result_count=1,
            unique_chunk_count=1,
            matches=[_match(rrf_k=60)],
        )


def test_response_requires_fused_score_then_chunk_id_order() -> None:
    equal_a = _match(
        "chunk-a",
        output_rank=2,
        semantic_rank=None,
        semantic_score=None,
    )
    equal_b = _match(
        "chunk-b",
        output_rank=1,
        semantic_rank=None,
        semantic_score=None,
    )
    with pytest.raises(ValidationError, match="fused score then chunk_id"):
        HybridRetrievalResponse(
            request=HybridRetrievalRequest(top_k=2),
            keyword_result_count=2,
            semantic_result_count=0,
            unique_chunk_count=2,
            matches=[equal_b, equal_a],
        )


def test_models_are_frozen_and_forbid_unknown_fields() -> None:
    request = HybridRetrievalRequest()
    with pytest.raises(ValidationError):
        request.top_k = 9
    with pytest.raises(ValidationError):
        HybridRetrievalRequest(unknown=True)
