"""Offline tests for deterministic document-chunk keyword retrieval."""

from __future__ import annotations

import pytest

from app.research.deterministic_keyword_retriever import (
    DeterministicKeywordRetriever,
    DeterministicKeywordRetrieverError,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.keyword_retrieval import KeywordRetrievalRequest


def _chunk(chunk_id: str, text: str, *, source_id: str = "source-1") -> DocumentChunk:
    return DocumentChunk(
        document_id=f"document-{chunk_id}",
        chunk_id=chunk_id,
        ordinal=0,
        text=text,
        start_char=0,
        end_char=len(text),
        metadata={"source_id": source_id},
    )


def test_scores_unique_query_token_coverage() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[
            _chunk("chunk-two", "Retrieval uses citations."),
            _chunk("chunk-one", "A source describes retrieval and citations."),
        ],
        request=KeywordRetrievalRequest(
            query="retrieval source citations",
            top_k=5,
        ),
    )

    assert [item.retrieval.chunk.chunk_id for item in response.matches] == [
        "chunk-one",
        "chunk-two",
    ]
    assert [item.retrieval.score for item in response.matches] == [1.0, 0.666667]
    assert response.matches[0].explanation.matched_terms == [
        "retrieval",
        "source",
        "citations",
    ]


def test_query_duplicates_do_not_inflate_score() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[_chunk("chunk-a", "Retrieval is traceable.")],
        request=KeywordRetrievalRequest(query="retrieval retrieval source"),
    )

    match = response.matches[0]
    assert match.explanation.query_tokens == ["retrieval", "source"]
    assert match.explanation.matched_terms == ["retrieval"]
    assert match.retrieval.score == 0.5


def test_normalizes_case_whitespace_and_unicode_compatibility() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[_chunk("chunk-a", "AIRA supports VERIFIED citations.")],
        request=KeywordRetrievalRequest(query="  ＡＩＲＡ\nverified  "),
    )

    assert response.matches[0].retrieval.score == 1.0
    assert response.matches[0].explanation.query_tokens == ["aira", "verified"]


def test_supports_korean_tokens() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[_chunk("chunk-ko", "검증된 출처 인용을 보존한다.")],
        request=KeywordRetrievalRequest(query="검증된 출처"),
    )

    assert response.matches[0].retrieval.score == 1.0
    assert response.matches[0].explanation.matched_terms == ["검증된", "출처"]


def test_records_exact_phrase_without_score_boost() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[
            _chunk("chunk-phrase", "Use exact source citations here."),
            _chunk("chunk-separated", "Source text has reliable citations."),
        ],
        request=KeywordRetrievalRequest(query="source citations"),
    )

    by_id = {item.retrieval.chunk.chunk_id: item for item in response.matches}
    assert by_id["chunk-phrase"].explanation.exact_phrase_match is True
    assert by_id["chunk-separated"].explanation.exact_phrase_match is False
    assert by_id["chunk-phrase"].retrieval.score == 1.0
    assert by_id["chunk-separated"].retrieval.score == 1.0


def test_equal_scores_use_chunk_id_tie_break() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[
            _chunk("chunk-b", "retrieval"),
            _chunk("chunk-a", "retrieval"),
        ],
        request=KeywordRetrievalRequest(query="retrieval source"),
    )

    assert [item.retrieval.chunk.chunk_id for item in response.matches] == [
        "chunk-a",
        "chunk-b",
    ]
    assert [item.retrieval.rank for item in response.matches] == [1, 2]


def test_applies_minimum_score_before_top_k() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[
            _chunk("chunk-full", "retrieval source citations"),
            _chunk("chunk-partial", "retrieval source"),
            _chunk("chunk-low", "retrieval only"),
        ],
        request=KeywordRetrievalRequest(
            query="retrieval source citations",
            top_k=1,
            minimum_score=0.5,
        ),
    )

    assert [item.retrieval.chunk.chunk_id for item in response.matches] == [
        "chunk-full"
    ]


def test_excludes_chunks_without_matching_terms() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[_chunk("chunk-a", "unrelated material")],
        request=KeywordRetrievalRequest(query="retrieval source"),
    )
    assert response.matches == []
    assert response.corpus_chunk_count == 1


def test_empty_corpus_returns_empty_response() -> None:
    response = DeterministicKeywordRetriever().search(
        chunks=[],
        request=KeywordRetrievalRequest(query="retrieval"),
    )
    assert response.matches == []
    assert response.corpus_chunk_count == 0


def test_preserves_exact_chunk_and_source_metadata() -> None:
    chunk = _chunk(
        "chunk-a",
        "retrieval source",
        source_id="source-academic",
    )
    response = DeterministicKeywordRetriever().search(
        chunks=[chunk],
        request=KeywordRetrievalRequest(query="retrieval"),
    )
    retrieved = response.matches[0].retrieval.chunk
    assert retrieved is chunk
    assert retrieved.metadata["source_id"] == "source-academic"
    assert retrieved.text == chunk.text
    assert (retrieved.start_char, retrieved.end_char) == (0, len(chunk.text))


def test_rejects_duplicate_corpus_chunk_ids_case_insensitively() -> None:
    with pytest.raises(
        DeterministicKeywordRetrieverError,
        match="corpus chunk IDs must be unique",
    ):
        DeterministicKeywordRetriever().search(
            chunks=[
                _chunk("chunk-a", "retrieval"),
                _chunk("CHUNK-A", "source"),
            ],
            request=KeywordRetrievalRequest(query="retrieval source"),
        )


def test_rejects_query_without_searchable_tokens() -> None:
    with pytest.raises(
        DeterministicKeywordRetrieverError,
        match="at least one searchable token",
    ):
        DeterministicKeywordRetriever().search(
            chunks=[_chunk("chunk-a", "retrieval")],
            request=KeywordRetrievalRequest(query="___---"),
        )


def test_same_input_produces_identical_response() -> None:
    chunks = [
        _chunk("chunk-b", "retrieval citations"),
        _chunk("chunk-a", "retrieval source"),
    ]
    request = KeywordRetrievalRequest(query="retrieval source citations")
    retriever = DeterministicKeywordRetriever()

    assert retriever.search(chunks=chunks, request=request) == retriever.search(
        chunks=chunks,
        request=request,
    )
