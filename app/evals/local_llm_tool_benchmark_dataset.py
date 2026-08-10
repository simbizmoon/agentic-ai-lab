"""AIRA-native local LLM tool selection and calling benchmark cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.tools.tool_registry import get_allowed_tool_schemas


class ToolSelectionOutput(BaseModel):
    """Strict deterministic output for tool-selection evaluation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_name: (
        Literal[
            "get_document_statistics",
            "extract_document_keywords",
        ]
        | None
    )


@dataclass(frozen=True)
class LocalLLMToolBenchmarkCase:
    """One AIRA-native tool benchmark case."""

    case_id: str
    user_request: str
    expected_tool_name: str | None
    expected_arguments: dict[str, Any] | None


def local_llm_tool_benchmark_cases() -> tuple[LocalLLMToolBenchmarkCase, ...]:
    """Return fixed tool-selection and native-calling cases."""
    return (
        LocalLLMToolBenchmarkCase(
            case_id="statistics-001",
            user_request=(
                "다음 문서의 정확한 문자 수, 단어 수, 줄 수를 계산해줘.\n"
                "문서:\n"
                "Agent tools are useful.\nThey execute code."
            ),
            expected_tool_name="get_document_statistics",
            expected_arguments={
                "document_text": (
                    "Agent tools are useful.\nThey execute code."
                ),
            },
        ),
        LocalLLMToolBenchmarkCase(
            case_id="keywords-001",
            user_request=(
                "다음 문서에서 가장 빈도가 높은 키워드 2개를 추출해줘.\n"
                "문서:\n"
                "agent tool agent workflow"
            ),
            expected_tool_name="extract_document_keywords",
            expected_arguments={
                "document_text": "agent tool agent workflow",
                "max_keywords": 2,
            },
        ),
        LocalLLMToolBenchmarkCase(
            case_id="direct-001",
            user_request=(
                "로컬 도구를 사용하는 것의 장점을 한 문장으로 설명해줘."
            ),
            expected_tool_name=None,
            expected_arguments=None,
        ),
        LocalLLMToolBenchmarkCase(
            case_id="multiple-ops-001",
            user_request=(
                "다음 문서의 정확한 통계도 계산하고 키워드 2개도 추출해줘.\n"
                "문서:\n"
                "agent tool agent workflow"
            ),
            expected_tool_name=None,
            expected_arguments=None,
        ),
    )


def ollama_tool_schemas() -> list[dict[str, Any]]:
    """Convert existing AIRA OpenAI-style schemas to Ollama chat schemas."""
    converted: list[dict[str, Any]] = []

    for schema in get_allowed_tool_schemas():
        function_schema = {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema["parameters"],
        }
        converted.append(
            {
                "type": "function",
                "function": function_schema,
            }
        )

    return converted


def tool_selection_prompt(user_request: str) -> str:
    """Build deterministic tool-selection prompt from AIRA registry policy."""
    tool_lines = []
    for schema in get_allowed_tool_schemas():
        tool_lines.append(
            f"- {schema['name']}: {schema.get('description', '')}"
        )

    tools = "\n".join(tool_lines)
    return (
        "너는 AIRA의 도구 선택기다.\n"
        "사용 가능한 도구:\n"
        f"{tools}\n\n"
        "규칙:\n"
        "- 정확한 문자/단어/줄 수 계산 요청은 "
        "get_document_statistics를 선택한다.\n"
        "- 빈도 기반 문서 키워드 추출 요청은 "
        "extract_document_keywords를 선택한다.\n"
        "- 도구가 필요 없는 요청은 tool_name을 null로 둔다.\n"
        "- 서로 다른 두 도구가 동시에 필요한 요청은 현재 workflow가 "
        "한 번에 하나의 도구만 지원하므로 tool_name을 null로 둔다.\n"
        "- 반드시 제공된 JSON Schema에 맞는 결과만 반환한다.\n\n"
        "사용자 요청:\n"
        f"{user_request}"
    )
