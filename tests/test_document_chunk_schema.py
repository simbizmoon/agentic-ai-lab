"""Tests for the document Chunk schema."""

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk


def test_document_chunk_accepts_valid_data() -> None:
    chunk = DocumentChunk(
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        ordinal=0,
        text="hello",
        start_char=0,
        end_char=5,
        metadata={"source": "example.txt"},
    )

    assert chunk.document_id == "doc-1"
    assert chunk.ordinal == 0
    assert chunk.text == "hello"
    assert chunk.start_char == 0
    assert chunk.end_char == 5
    assert chunk.metadata == {
        "source": "example.txt",
    }


def test_document_chunk_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        DocumentChunk(
            document_id="doc-1",
            chunk_id="doc-1:chunk:0000",
            ordinal=0,
            text="hello",
            start_char=0,
            end_char=5,
            unknown_field="not allowed",
        )


def test_document_chunk_rejects_negative_ordinal() -> None:
    with pytest.raises(ValidationError):
        DocumentChunk(
            document_id="doc-1",
            chunk_id="doc-1:chunk:0000",
            ordinal=-1,
            text="hello",
            start_char=0,
            end_char=5,
        )


def test_document_chunk_rejects_invalid_range() -> None:
    with pytest.raises(
        ValidationError,
        match="end_char must be greater",
    ):
        DocumentChunk(
            document_id="doc-1",
            chunk_id="doc-1:chunk:0000",
            ordinal=0,
            text="hello",
            start_char=5,
            end_char=5,
        )


def test_document_chunk_rejects_range_length_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="text length must match",
    ):
        DocumentChunk(
            document_id="doc-1",
            chunk_id="doc-1:chunk:0000",
            ordinal=0,
            text="hello",
            start_char=0,
            end_char=10,
        )


def test_document_chunk_metadata_defaults_to_empty_dict() -> None:
    chunk = DocumentChunk(
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        ordinal=0,
        text="hello",
        start_char=0,
        end_char=5,
    )

    assert chunk.metadata == {}
