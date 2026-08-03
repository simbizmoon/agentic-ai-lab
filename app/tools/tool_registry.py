"""Explicit registry of locally allowed tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.tools.document_keywords import (
    DocumentKeywordsInput,
    extract_document_keywords,
)
from app.tools.document_keywords_schema import (
    DOCUMENT_KEYWORDS_TOOL,
)
from app.tools.document_statistics import (
    DocumentStatisticsInput,
    get_document_statistics,
)
from app.tools.document_statistics_schema import (
    DOCUMENT_STATISTICS_TOOL,
)

ToolExecutor = Callable[[BaseModel], BaseModel]


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of one explicitly allowed local Tool."""

    name: str
    input_model: type[BaseModel]
    executor: ToolExecutor
    schema: dict[str, Any]
    read_only: bool
    requires_approval: bool

    def __post_init__(self) -> None:
        """Reject unsafe or inconsistent Tool policies."""

        if not self.name.strip():
            raise ValueError("tool name must not be empty")

        schema_name = self.schema.get("name")

        if schema_name != self.name:
            raise ValueError(
                "tool schema name must match ToolDefinition name"
            )

        if not self.read_only and not self.requires_approval:
            raise ValueError(
                "state-changing tools must require human approval"
            )


DOCUMENT_KEYWORDS_DEFINITION = ToolDefinition(
    name="extract_document_keywords",
    input_model=DocumentKeywordsInput,
    executor=extract_document_keywords,
    schema=DOCUMENT_KEYWORDS_TOOL,
    read_only=True,
    requires_approval=False,
)


DOCUMENT_STATISTICS_DEFINITION = ToolDefinition(
    name="get_document_statistics",
    input_model=DocumentStatisticsInput,
    executor=get_document_statistics,
    schema=DOCUMENT_STATISTICS_TOOL,
    read_only=True,
    requires_approval=False,
)


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    DOCUMENT_STATISTICS_DEFINITION.name: (
        DOCUMENT_STATISTICS_DEFINITION
    ),
    DOCUMENT_KEYWORDS_DEFINITION.name: (
        DOCUMENT_KEYWORDS_DEFINITION
    ),
}


def get_allowed_tool(
    tool_name: str,
) -> ToolDefinition | None:
    """Return an explicitly allowed Tool definition."""

    return TOOL_REGISTRY.get(tool_name)


def get_allowed_tool_schemas() -> list[dict[str, Any]]:
    """Return schemas for all explicitly allowed local Tools."""

    return [
        definition.schema
        for definition in TOOL_REGISTRY.values()
    ]
