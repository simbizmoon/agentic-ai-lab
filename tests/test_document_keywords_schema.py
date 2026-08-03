"""Tests for the document keyword Tool schema."""

from app.tools.document_keywords_schema import (
    DOCUMENT_KEYWORDS_TOOL,
)


def test_keyword_tool_schema_identity() -> None:
    assert DOCUMENT_KEYWORDS_TOOL["type"] == "function"
    assert (
        DOCUMENT_KEYWORDS_TOOL["name"]
        == "extract_document_keywords"
    )
    assert DOCUMENT_KEYWORDS_TOOL["strict"] is True


def test_keyword_tool_schema_requires_expected_arguments() -> None:
    parameters = DOCUMENT_KEYWORDS_TOOL["parameters"]

    assert parameters["type"] == "object"
    assert set(parameters["required"]) == {
        "document_text",
        "max_keywords",
    }
    assert parameters["additionalProperties"] is False


def test_keyword_tool_schema_limits_max_keywords() -> None:
    max_keywords = DOCUMENT_KEYWORDS_TOOL[
        "parameters"
    ]["properties"]["max_keywords"]

    assert max_keywords["type"] == "integer"
    assert max_keywords["minimum"] == 1
    assert max_keywords["maximum"] == 20
