"""Offline tests for deterministic reciprocal-rank fusion runtime."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.research.deterministic_hybrid_retriever import (
    DeterministicHybridRetriever,
    DeterministicHybridRetrieverError,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.hybrid_retrieval import HybridRetrievalRequest
from app.schemas.retrieval_result import RetrievalResult


def _chunk(
    chunk_id: str,
    *,
    text: str | None = None,
    metadata: dict[str, object] | None = None,
) -> DocumentChunk:
    value = text or f"Exact evidence for {chunk_id}."
    return DocumentChunk(
        document_id=f"document-{chunk_id}",
        chunk_id=chunk_id,
        ordinal=0,
        text=value,
        start_char=0,
        end_char=len(value),
        metadata=metadata or {"source_id": f"source-{chunk_id}"},
    )


def _result(
    chunk_id: str,
    *,
    rank: int,
    score: float,
    chunk: DocumentChunk | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk=chunk or _chunk(chunk_id),
        rank=rank,
        score=score,
    )


def _fuse(
    keyword: list[RetrievalResult],
    semantic: list[RetrievalResult],
    *,
    top_k: int = 5,
    rrf_k: int = 60,
):
    return DeterministicHybridRetriever().fuse(
        keyword_results=keyword,
        semantic_results=semantic,
        request=HybridRetrievalRequest(top_k=top_k, rrf_k=rrf_k),
    )


def test_empty_channels_produce_empty_response() -> None:
    response = _fuse([], [])
    assert response.keyword_result_count == 0
    assert response.semantic_result_count == 0
    assert response.unique_chunk_count == 0
    assert response.matches == []


def test_same_chunk_in_both_channels_combines_ranks_not_raw_scores() -> None:
    chunk = _chunk("chunk-a")
    response = _fuse(
        [_result("chunk-a", rank=1, score=0.2, chunk=chunk)],
        [
            _result("semantic-first", rank=1, score=1.0),
            _result("chunk-a", rank=2, score=0.99, chunk=chunk),
        ],
    )
    match = next(
        item for item in response.matches if item.retrieval.chunk.chunk_id == "chunk-a"
    )
    assert match.retrieval.chunk is chunk
    assert match.keyword_score == 0.2
    assert match.semantic_score == 0.99
    assert match.keyword_contribution == pytest.approx(1 / 61)
    assert match.semantic_contribution == pytest.approx(1 / 62)
    assert match.fused_score == pytest.approx((1 / 61) + (1 / 62))
    assert match.matched_channel_count == 2


def test_results_found_by_both_channels_rank_above_single_channel() -> None:
    shared = _chunk("chunk-shared")
    response = _fuse(
        [
            _result("chunk-keyword", rank=1, score=1.0),
            _result("chunk-shared", rank=2, score=0.5, chunk=shared),
        ],
        [
            _result("chunk-semantic", rank=1, score=1.0),
            _result("chunk-shared", rank=2, score=0.7, chunk=shared),
        ],
    )
    assert [item.retrieval.chunk.chunk_id for item in response.matches] == [
        "chunk-shared",
        "chunk-keyword",
        "chunk-semantic",
    ]


def test_channel_only_results_keep_absence_explicit() -> None:
    response = _fuse(
        [_result("keyword-only", rank=1, score=0.8)],
        [_result("semantic-only", rank=1, score=-0.2)],
    )
    by_id = {item.retrieval.chunk.chunk_id: item for item in response.matches}
    assert by_id["keyword-only"].semantic_rank is None
    assert by_id["keyword-only"].semantic_contribution is None
    assert by_id["semantic-only"].keyword_rank is None
    assert by_id["semantic-only"].keyword_contribution is None


def test_equal_fused_scores_use_chunk_id_without_channel_preference() -> None:
    response = _fuse(
        [_result("chunk-z", rank=1, score=1.0)],
        [_result("chunk-a", rank=1, score=1.0)],
    )
    assert [item.retrieval.chunk.chunk_id for item in response.matches] == [
        "chunk-a",
        "chunk-z",
    ]


def test_top_k_is_applied_after_union_and_ranks_are_reassigned() -> None:
    response = _fuse(
        [
            _result("chunk-a", rank=1, score=1.0),
            _result("chunk-b", rank=2, score=0.5),
        ],
        [
            _result("chunk-c", rank=1, score=1.0),
            _result("chunk-d", rank=2, score=0.5),
        ],
        top_k=2,
    )
    assert response.unique_chunk_count == 4
    assert len(response.matches) == 2
    assert [item.retrieval.rank for item in response.matches] == [1, 2]


def test_custom_rrf_k_is_used_in_every_contribution() -> None:
    response = _fuse(
        [_result("chunk-a", rank=1, score=1.0)],
        [_result("chunk-b", rank=1, score=1.0)],
        rrf_k=10,
    )
    assert all(item.rrf_k == 10 for item in response.matches)
    assert all(item.fused_score == pytest.approx(1 / 11) for item in response.matches)


def test_conflicting_chunk_payload_for_same_identity_is_rejected() -> None:
    with pytest.raises(DeterministicHybridRetrieverError, match="conflicting chunks"):
        _fuse(
            [_result("chunk-a", rank=1, score=1.0)],
            [
                _result(
                    "chunk-a",
                    rank=1,
                    score=1.0,
                    chunk=_chunk("chunk-a", text="Different text."),
                )
            ],
        )


def test_case_insensitive_identity_with_different_exact_id_is_conflict() -> None:
    with pytest.raises(DeterministicHybridRetrieverError, match="conflicting chunks"):
        _fuse(
            [_result("chunk-a", rank=1, score=1.0)],
            [_result("CHUNK-A", rank=1, score=1.0)],
        )


@pytest.mark.parametrize("channel", ["keyword", "semantic"])
def test_each_channel_requires_contiguous_ranks_in_input_order(channel: str) -> None:
    invalid = [_result("chunk-a", rank=2, score=0.5)]
    with pytest.raises(DeterministicHybridRetrieverError, match="contiguous"):
        _fuse(
            invalid if channel == "keyword" else [],
            invalid if channel == "semantic" else [],
        )


@pytest.mark.parametrize("channel", ["keyword", "semantic"])
def test_each_channel_rejects_duplicate_chunk_ids(channel: str) -> None:
    duplicate = [
        _result("chunk-a", rank=1, score=1.0),
        _result("CHUNK-A", rank=2, score=0.5),
    ]
    with pytest.raises(DeterministicHybridRetrieverError, match="must be unique"):
        _fuse(
            duplicate if channel == "keyword" else [],
            duplicate if channel == "semantic" else [],
        )


def test_keyword_channel_rejects_negative_score() -> None:
    with pytest.raises(DeterministicHybridRetrieverError, match="must not be negative"):
        _fuse([_result("chunk-a", rank=1, score=-0.1)], [])


def test_semantic_channel_preserves_negative_cosine_score() -> None:
    response = _fuse([], [_result("chunk-a", rank=1, score=-1.0)])
    assert response.matches[0].semantic_score == -1.0
    assert response.matches[0].fused_score == pytest.approx(1 / 61)


def test_inputs_are_not_mutated() -> None:
    keyword = [_result("chunk-a", rank=1, score=1.0)]
    semantic = [_result("chunk-b", rank=1, score=0.5)]
    keyword_before = deepcopy(keyword)
    semantic_before = deepcopy(semantic)
    _fuse(keyword, semantic)
    assert keyword == keyword_before
    assert semantic == semantic_before


def test_request_type_is_validated() -> None:
    with pytest.raises(TypeError, match="HybridRetrievalRequest"):
        DeterministicHybridRetriever().fuse(
            keyword_results=[],
            semantic_results=[],
            request="invalid",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("channel", ["keyword", "semantic"])
def test_channel_collection_rejects_string(channel: str) -> None:
    with pytest.raises(TypeError, match="sequence of RetrievalResult"):
        DeterministicHybridRetriever().fuse(
            keyword_results="invalid" if channel == "keyword" else [],  # type: ignore[arg-type]
            semantic_results="invalid" if channel == "semantic" else [],  # type: ignore[arg-type]
            request=HybridRetrievalRequest(),
        )


def test_output_preserves_exact_chunk_provenance() -> None:
    chunk = _chunk(
        "chunk-a",
        metadata={
            "source_id": "source-exact",
            "source_type": "academic",
            "response_sha256": "a" * 64,
        },
    )
    response = _fuse(
        [_result("chunk-a", rank=1, score=1.0, chunk=chunk)],
        [_result("chunk-a", rank=1, score=0.9, chunk=chunk)],
    )
    assert response.matches[0].retrieval.chunk == chunk
    assert response.matches[0].retrieval.chunk.metadata == chunk.metadata
