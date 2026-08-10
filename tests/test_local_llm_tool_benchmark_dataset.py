"""Tests for AIRA-native local LLM tool benchmark dataset."""

from app.evals.local_llm_tool_benchmark_dataset import (
    local_llm_tool_benchmark_cases,
    ollama_tool_schemas,
)


def test_cases_are_stable() -> None:
    cases = local_llm_tool_benchmark_cases()

    assert [case.case_id for case in cases] == [
        "statistics-001",
        "keywords-001",
        "direct-001",
        "multiple-ops-001",
    ]


def test_cases_cover_two_tools_and_no_tool() -> None:
    expected = {
        case.expected_tool_name
        for case in local_llm_tool_benchmark_cases()
    }

    assert expected == {
        "get_document_statistics",
        "extract_document_keywords",
        None,
    }


def test_ollama_tool_schemas_reuse_aira_registry() -> None:
    tools = ollama_tool_schemas()

    assert [tool["function"]["name"] for tool in tools] == [
        "get_document_statistics",
        "extract_document_keywords",
    ]
    assert all(tool["type"] == "function" for tool in tools)
    assert all(
        tool["function"]["parameters"]["additionalProperties"] is False
        for tool in tools
    )
