"""Offline tests for deterministic keyword retrieval schemas."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.keyword_retrieval import (
    KeywordRetrievalExplanation,
    KeywordRetrievalMatch,
    KeywordRetrievalRequest,
    KeywordRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult


def _match(
    *,
    chunk_id: str,
    score: float,
    rank: int,
    matched_terms: list[str],
    phrase: bool = False,
) -> KeywordRetrievalMatch:
    query_tokens = ["retrieval", "source", "citations"]
    text = f"Text for {chunk_id} about {' '.join(matched_terms)}."
    return KeywordRetrievalMatch(
        retrieval=RetrievalResult(
            chunk=DocumentChunk(
                document_id=f"document-{chunk_id}",
                chunk_id=chunk_id,
                ordinal=0,
                text=text,
                start_char=0,
                end_char=len(text),
            ),
            score=score,
            rank=rank,
        ),
        explanation=KeywordRetrievalExplanation(
            query_tokens=query_tokens,
            matched_terms=matched_terms,
            token_coverage=len(matched_terms) / len(query_tokens),
            exact_phrase_match=phrase,
        ),
    )


def test_request_accepts_bounded_values() -> None:
    request = KeywordRetrievalRequest(
        query="retrieval source citations",
        top_k=10,
        minimum_score=0.25,
    )
    assert request.top_k == 10
    assert request.minimum_score == 0.25


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_request_rejects_blank_query(query: str) -> None:
    with pytest.raises(ValidationError, match="query must not be blank"):
        KeywordRetrievalRequest(query=query)


@pytest.mark.parametrize("top_k", [0, 101])
def test_request_rejects_unbounded_top_k(top_k: int) -> None:
    with pytest.raises(ValidationError):
        KeywordRetrievalRequest(query="retrieval", top_k=top_k)


def test_request_rejects_nonfinite_minimum_score() -> None:
    with pytest.raises(ValidationError, match="minimum_score must be finite"):
        KeywordRetrievalRequest(query="retrieval", minimum_score=math.nan)


def test_explanation_accepts_auditable_coverage() -> None:
    explanation = KeywordRetrievalExplanation(
        query_tokens=["retrieval", "source", "citations"],
        matched_terms=["retrieval", "citations"],
        token_coverage=2 / 3,
        exact_phrase_match=False,
    )
    assert explanation.token_coverage == pytest.approx(2 / 3)


def test_explanation_rejects_wrong_coverage() -> None:
    with pytest.raises(ValidationError, match="token_coverage must equal"):
        KeywordRetrievalExplanation(
            query_tokens=["retrieval", "source"],
            matched_terms=["retrieval"],
            token_coverage=0.75,
            exact_phrase_match=False,
        )


def test_explanation_rejects_term_outside_query() -> None:
    with pytest.raises(ValidationError, match="subset of query_tokens"):
        KeywordRetrievalExplanation(
            query_tokens=["retrieval", "source"],
            matched_terms=["unrelated"],
            token_coverage=0.5,
            exact_phrase_match=False,
        )


@pytest.mark.parametrize(
    ("field", "values", "message"),
    [
        ("query_tokens", ["retrieval", "Retrieval"], "query_tokens.*duplicates"),
        ("matched_terms", ["source", "SOURCE"], "matched_terms.*duplicates"),
        ("matched_terms", [" "], "matched_terms.*blank"),
    ],
)
def test_explanation_rejects_invalid_token_lists(
    field: str,
    values: list[str],
    message: str,
) -> None:
    data = {
        "query_tokens": ["retrieval", "source"],
        "matched_terms": ["source"],
        "token_coverage": 0.5,
        "exact_phrase_match": False,
    }
    data[field] = values
    with pytest.raises(ValidationError, match=message):
        KeywordRetrievalExplanation(**data)


def test_match_reuses_standard_retrieval_result() -> None:
    match = _match(
        chunk_id="chunk-a",
        score=2 / 3,
        rank=1,
        matched_terms=["retrieval", "source"],
    )
    assert match.retrieval.chunk.chunk_id == "chunk-a"
    assert match.explanation.matched_terms == ["retrieval", "source"]


def test_match_rejects_empty_lexical_signal() -> None:
    with pytest.raises(ValidationError, match="must contain a matched term"):
        _match(chunk_id="chunk-a", score=0.0, rank=1, matched_terms=[])


def test_response_accepts_score_then_chunk_id_order() -> None:
    response = KeywordRetrievalResponse(
        request=KeywordRetrievalRequest(
            query="retrieval source citations",
            top_k=3,
            minimum_score=0.3,
        ),
        corpus_chunk_count=5,
        matches=[
            _match(
                chunk_id="chunk-a",
                score=2 / 3,
                rank=1,
                matched_terms=["retrieval", "source"],
            ),
            _match(
                chunk_id="chunk-b",
                score=1 / 3,
                rank=2,
                matched_terms=["citations"],
            ),
        ],
    )
    assert [item.retrieval.rank for item in response.matches] == [1, 2]


def test_response_rejects_nondeterministic_tie_order() -> None:
    with pytest.raises(ValidationError, match="descending score then chunk_id"):
        KeywordRetrievalResponse(
            request=KeywordRetrievalRequest(query="retrieval source citations"),
            corpus_chunk_count=2,
            matches=[
                _match(
                    chunk_id="chunk-b",
                    score=1 / 3,
                    rank=1,
                    matched_terms=["retrieval"],
                ),
                _match(
                    chunk_id="chunk-a",
                    score=1 / 3,
                    rank=2,
                    matched_terms=["source"],
                ),
            ],
        )


def test_response_rejects_noncontiguous_ranks() -> None:
    with pytest.raises(ValidationError, match="contiguous from one"):
        KeywordRetrievalResponse(
            request=KeywordRetrievalRequest(query="retrieval source citations"),
            corpus_chunk_count=1,
            matches=[
                _match(
                    chunk_id="chunk-a",
                    score=1 / 3,
                    rank=2,
                    matched_terms=["retrieval"],
                )
            ],
        )


def test_response_rejects_score_below_request_minimum() -> None:
    with pytest.raises(ValidationError, match="satisfy request minimum_score"):
        KeywordRetrievalResponse(
            request=KeywordRetrievalRequest(
                query="retrieval source citations",
                minimum_score=0.5,
            ),
            corpus_chunk_count=1,
            matches=[
                _match(
                    chunk_id="chunk-a",
                    score=1 / 3,
                    rank=1,
                    matched_terms=["retrieval"],
                )
            ],
        )


def test_response_rejects_duplicate_chunks() -> None:
    with pytest.raises(ValidationError, match="chunk IDs must be unique"):
        KeywordRetrievalResponse(
            request=KeywordRetrievalRequest(query="retrieval source citations"),
            corpus_chunk_count=2,
            matches=[
                _match(
                    chunk_id="chunk-a",
                    score=2 / 3,
                    rank=1,
                    matched_terms=["retrieval", "source"],
                ),
                _match(
                    chunk_id="chunk-a",
                    score=1 / 3,
                    rank=2,
                    matched_terms=["citations"],
                ),
            ],
        )


def test_response_rejects_unknown_ranking_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        KeywordRetrievalResponse(
            request=KeywordRetrievalRequest(query="retrieval"),
            corpus_chunk_count=0,
            matches=[],
            winner="chunk-a",
        )
