"""Tests for the document statistics OpenAI tool schema."""

from app.tools.document_statistics_schema import (
    DOCUMENT_STATISTICS_TOOL,
)


def test_document_statistics_tool_has_expected_identity() -> None:
    assert DOCUMENT_STATISTICS_TOOL["type"] == "function"
    assert (
        DOCUMENT_STATISTICS_TOOL["name"]
        == "get_document_statistics"
    )
    assert DOCUMENT_STATISTICS_TOOL["strict"] is True


def test_document_statistics_tool_requires_document_text() -> None:
    parameters = DOCUMENT_STATISTICS_TOOL["parameters"]

    assert parameters["type"] == "object"
    assert parameters["required"] == ["document_text"]
    assert parameters["additionalProperties"] is False


def test_document_statistics_tool_document_text_is_string() -> None:
    document_text = DOCUMENT_STATISTICS_TOOL[
        "parameters"
    ]["properties"]["document_text"]

    assert document_text["type"] == "string"
    assert document_text["minLength"] == 1
