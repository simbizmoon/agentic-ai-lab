"""Tests for the in-memory Vector Store."""

import pytest

from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.rag.vector_store import VectorStoreError
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import (
    EmbeddedDocumentChunk,
    TextEmbedding,
)


def embedded_chunk(
    *,
    chunk_id: str,
    ordinal: int,
    text: str,
    vector: list[float],
    model_name: str = "test-model",
) -> EmbeddedDocumentChunk:
    """Create an embedded Chunk for Vector Store tests."""

    return EmbeddedDocumentChunk(
        chunk=DocumentChunk(
            document_id="doc-1",
            chunk_id=chunk_id,
            ordinal=ordinal,
            text=text,
            start_char=0,
            end_char=len(text),
        ),
        embedding=TextEmbedding(
            model_name=model_name,
            dimensions=len(vector),
            vector=vector,
        ),
    )


def query_embedding(
    vector: list[float],
    *,
    model_name: str = "test-model",
) -> TextEmbedding:
    """Create a query embedding."""

    return TextEmbedding(
        model_name=model_name,
        dimensions=len(vector),
        vector=vector,
    )


def test_store_starts_empty() -> None:
    store = InMemoryVectorStore()

    assert store.count() == 0
    assert store.search(
        query_embedding=query_embedding([1.0, 0.0]),
    ) == []


def test_add_stores_items() -> None:
    store = InMemoryVectorStore()

    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
            ),
            embedded_chunk(
                chunk_id="chunk-2",
                ordinal=1,
                text="second",
                vector=[0.0, 1.0],
            ),
        ]
    )

    assert store.count() == 2


def test_add_replaces_existing_chunk_id() -> None:
    store = InMemoryVectorStore()

    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="original",
                vector=[1.0, 0.0],
            )
        ]
    )
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="replacement",
                vector=[0.0, 1.0],
            )
        ]
    )

    results = store.search(
        query_embedding=query_embedding([0.0, 1.0]),
    )

    assert store.count() == 1
    assert results[0].chunk.text == "replacement"


def test_search_orders_results_by_similarity() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-exact",
                ordinal=0,
                text="exact",
                vector=[1.0, 0.0],
            ),
            embedded_chunk(
                chunk_id="chunk-related",
                ordinal=1,
                text="related",
                vector=[0.8, 0.2],
            ),
            embedded_chunk(
                chunk_id="chunk-opposite",
                ordinal=2,
                text="opposite",
                vector=[-1.0, 0.0],
            ),
        ]
    )

    results = store.search(
        query_embedding=query_embedding([1.0, 0.0]),
        top_k=3,
    )

    assert [
        result.chunk.chunk_id
        for result in results
    ] == [
        "chunk-exact",
        "chunk-related",
        "chunk-opposite",
    ]
    assert [result.rank for result in results] == [
        1,
        2,
        3,
    ]
    assert results[0].score == pytest.approx(1.0)
    assert results[2].score == pytest.approx(-1.0)


def test_search_respects_top_k() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
            ),
            embedded_chunk(
                chunk_id="chunk-2",
                ordinal=1,
                text="second",
                vector=[0.8, 0.2],
            ),
            embedded_chunk(
                chunk_id="chunk-3",
                ordinal=2,
                text="third",
                vector=[0.0, 1.0],
            ),
        ]
    )

    results = store.search(
        query_embedding=query_embedding([1.0, 0.0]),
        top_k=2,
    )

    assert len(results) == 2
    assert [result.rank for result in results] == [
        1,
        2,
    ]


def test_equal_scores_are_ordered_by_chunk_id() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-b",
                ordinal=1,
                text="second",
                vector=[1.0, 0.0],
            ),
            embedded_chunk(
                chunk_id="chunk-a",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
            ),
        ]
    )

    results = store.search(
        query_embedding=query_embedding([1.0, 0.0]),
        top_k=2,
    )

    assert [
        result.chunk.chunk_id
        for result in results
    ] == [
        "chunk-a",
        "chunk-b",
    ]


@pytest.mark.parametrize("top_k", [0, -1])
def test_search_rejects_invalid_top_k(
    top_k: int,
) -> None:
    store = InMemoryVectorStore()

    with pytest.raises(
        VectorStoreError,
        match="top_k must be greater than zero",
    ):
        store.search(
            query_embedding=query_embedding(
                [1.0, 0.0]
            ),
            top_k=top_k,
        )


def test_search_rejects_dimension_mismatch() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
            )
        ]
    )

    with pytest.raises(
        VectorStoreError,
        match="matching dimensions",
    ):
        store.search(
            query_embedding=query_embedding(
                [1.0, 0.0, 0.0]
            ),
        )


def test_search_rejects_model_mismatch() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
                model_name="stored-model",
            )
        ]
    )

    with pytest.raises(
        VectorStoreError,
        match="same model",
    ):
        store.search(
            query_embedding=query_embedding(
                [1.0, 0.0],
                model_name="query-model",
            ),
        )


def test_clear_removes_all_items() -> None:
    store = InMemoryVectorStore()
    store.add(
        [
            embedded_chunk(
                chunk_id="chunk-1",
                ordinal=0,
                text="first",
                vector=[1.0, 0.0],
            )
        ]
    )

    store.clear()

    assert store.count() == 0
