"""Tests for the deterministic document statistics tool."""

import pytest
from pydantic import ValidationError

from app.tools.document_statistics import (
    DocumentStatisticsInput,
    get_document_statistics,
)


def test_get_document_statistics_returns_expected_counts() -> None:
    tool_input = DocumentStatisticsInput(
        document_text="Agent tools are useful.\nThey execute code."
    )

    result = get_document_statistics(tool_input)

    assert result.character_count == 42
    assert result.word_count == 7
    assert result.line_count == 2


def test_get_document_statistics_counts_single_line() -> None:
    tool_input = DocumentStatisticsInput(
        document_text="single line"
    )

    result = get_document_statistics(tool_input)

    assert result.character_count == 11
    assert result.word_count == 2
    assert result.line_count == 1


def test_document_statistics_input_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        DocumentStatisticsInput(document_text="")


def test_document_statistics_input_rejects_whitespace_only_text() -> None:
    with pytest.raises(ValidationError):
        DocumentStatisticsInput(document_text=" \n\t ")


def test_document_statistics_input_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentStatisticsInput(
            document_text="valid text",
            unsupported=True,
        )
