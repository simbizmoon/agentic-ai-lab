"""Normalize Pydantic schemas for OpenAI strict Structured Outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def to_openai_strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with every object closed and every property required."""

    if not isinstance(schema, dict):
        raise TypeError("schema must be a dictionary")
    normalized = deepcopy(schema)
    _normalize_node(normalized)
    return normalized


def _normalize_node(node: object) -> None:
    if isinstance(node, list):
        for item in node:
            _normalize_node(item)
        return
    if not isinstance(node, dict):
        return

    node.pop("default", None)
    properties = node.get("properties")
    if node.get("type") == "object" or isinstance(properties, dict):
        typed_properties = properties if isinstance(properties, dict) else {}
        node["additionalProperties"] = False
        node["required"] = list(typed_properties)

    for value in node.values():
        _normalize_node(value)
