"""Tests for deterministic document Chunking."""

import pytest

from app.rag.document_chunker import (
    DocumentChunkingError,
    chunk_document_text,
)


def test_short_document_creates_one_chunk() -> None:
    chunks = chunk_document_text(
        document_id="doc-1",
        text="short document",
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc-1:chunk:0000"
    assert chunks[0].ordinal == 0
    assert chunks[0].text == "short document"
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == 14


def test_document_is_split_with_overlap() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_document_text(
        document_id="alphabet",
        text=text,
        chunk_size=10,
        chunk_overlap=2,
    )

    assert [chunk.text for chunk in chunks] == [
        "abcdefghij",
        "ijklmnopqr",
        "qrstuvwxyz",
    ]
    assert [
        (chunk.start_char, chunk.end_char)
        for chunk in chunks
    ] == [
        (0, 10),
        (8, 18),
        (16, 26),
    ]


def test_chunk_ids_and_ordinals_are_deterministic() -> None:
    chunks = chunk_document_text(
        document_id="doc-42",
        text="0123456789ABCDEF",
        chunk_size=6,
        chunk_overlap=2,
    )

    assert [chunk.chunk_id for chunk in chunks] == [
        "doc-42:chunk:0000",
        "doc-42:chunk:0001",
        "doc-42:chunk:0002",
        "doc-42:chunk:0003",
    ]
    assert [chunk.ordinal for chunk in chunks] == [
        0,
        1,
        2,
        3,
    ]


def test_chunks_preserve_original_text_slices() -> None:
    text = "First line.\nSecond line.\nThird line."

    chunks = chunk_document_text(
        document_id="lines",
        text=text,
        chunk_size=12,
        chunk_overlap=3,
    )

    for chunk in chunks:
        assert chunk.text == text[
            chunk.start_char:chunk.end_char
        ]


def test_metadata_is_copied_to_each_chunk() -> None:
    chunks = chunk_document_text(
        document_id="doc-1",
        text="abcdefghijk",
        chunk_size=6,
        chunk_overlap=1,
        metadata={
            "source": "sample.txt",
            "category": "test",
        },
    )

    assert all(
        chunk.metadata == {
            "source": "sample.txt",
            "category": "test",
        }
        for chunk in chunks
    )

    assert chunks[0].metadata is not chunks[1].metadata


def test_same_input_produces_same_chunks() -> None:
    arguments = {
        "document_id": "stable-doc",
        "text": "A deterministic document example.",
        "chunk_size": 10,
        "chunk_overlap": 2,
    }

    first = chunk_document_text(**arguments)
    second = chunk_document_text(**arguments)

    assert first == second


@pytest.mark.parametrize(
    ("document_id", "text", "chunk_size", "chunk_overlap"),
    [
        ("", "document", 10, 2),
        ("   ", "document", 10, 2),
        ("doc-1", "", 10, 2),
        ("doc-1", "   ", 10, 2),
        ("doc-1", "document", 0, 0),
        ("doc-1", "document", -1, 0),
        ("doc-1", "document", 10, -1),
        ("doc-1", "document", 10, 10),
        ("doc-1", "document", 10, 11),
    ],
)
def test_invalid_chunking_input_is_rejected(
    document_id: str,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    with pytest.raises(DocumentChunkingError):
        chunk_document_text(
            document_id=document_id,
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
