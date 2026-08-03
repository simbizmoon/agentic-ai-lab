"""Tests for paragraph-aware document Chunking."""

import pytest

from app.rag.document_chunker import (
    DocumentChunkingError,
    chunk_document_by_paragraphs,
)


def test_short_paragraphs_are_grouped() -> None:
    text = "First paragraph.\n\nSecond paragraph."

    chunks = chunk_document_by_paragraphs(
        document_id="doc-1",
        text=text,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(text)


def test_chunking_prefers_paragraph_boundaries() -> None:
    text = (
        "Paragraph one."
        "\n\n"
        "Paragraph two."
        "\n\n"
        "Paragraph three."
    )

    chunks = chunk_document_by_paragraphs(
        document_id="doc-1",
        text=text,
        chunk_size=31,
        chunk_overlap=5,
    )

    assert [chunk.text for chunk in chunks] == [
        "Paragraph one.\n\nParagraph two.",
        "Paragraph three.",
    ]


def test_multiple_paragraph_chunks_preserve_source_ranges() -> None:
    text = (
        "Alpha paragraph."
        "\n\n"
        "Beta paragraph."
        "\n\n"
        "Gamma paragraph."
    )

    chunks = chunk_document_by_paragraphs(
        document_id="ranges",
        text=text,
        chunk_size=20,
        chunk_overlap=4,
    )

    for chunk in chunks:
        assert chunk.text == text[
            chunk.start_char:chunk.end_char
        ]


def test_long_paragraph_uses_character_chunking() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_document_by_paragraphs(
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


def test_long_paragraph_after_short_paragraph() -> None:
    text = "Intro.\n\nabcdefghijklmnopqrstuvwxyz"

    chunks = chunk_document_by_paragraphs(
        document_id="mixed",
        text=text,
        chunk_size=10,
        chunk_overlap=2,
    )

    assert chunks[0].text == "Intro."
    assert [chunk.text for chunk in chunks[1:]] == [
        "abcdefghij",
        "ijklmnopqr",
        "qrstuvwxyz",
    ]

    for chunk in chunks:
        assert chunk.text == text[
            chunk.start_char:chunk.end_char
        ]


def test_blank_paragraph_separators_are_preserved() -> None:
    text = "First.\n\n\n\nSecond."

    chunks = chunk_document_by_paragraphs(
        document_id="blank-lines",
        text=text,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_metadata_is_copied_to_paragraph_chunks() -> None:
    chunks = chunk_document_by_paragraphs(
        document_id="metadata",
        text="First paragraph.\n\nSecond paragraph.",
        chunk_size=20,
        chunk_overlap=3,
        metadata={"source": "sample.txt"},
    )

    assert len(chunks) == 2
    assert all(
        chunk.metadata == {"source": "sample.txt"}
        for chunk in chunks
    )
    assert chunks[0].metadata is not chunks[1].metadata


def test_paragraph_chunk_ids_are_deterministic() -> None:
    arguments = {
        "document_id": "stable",
        "text": "First.\n\nSecond.\n\nThird.",
        "chunk_size": 12,
        "chunk_overlap": 2,
    }

    first = chunk_document_by_paragraphs(**arguments)
    second = chunk_document_by_paragraphs(**arguments)

    assert first == second
    assert [chunk.chunk_id for chunk in first] == [
        "stable:chunk:0000",
        "stable:chunk:0001",
        "stable:chunk:0002",
    ]


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
def test_invalid_paragraph_chunking_input_is_rejected(
    document_id: str,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    with pytest.raises(DocumentChunkingError):
        chunk_document_by_paragraphs(
            document_id=document_id,
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
