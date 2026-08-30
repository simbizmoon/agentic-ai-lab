"""Normalize Pydantic schemas for OpenAI strict Structured Outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def to_openai_strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a strict copy, omitting defaulted free-form object fields."""

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

    properties = node.get("properties")
    if node.get("type") == "object" or isinstance(properties, dict):
        typed_properties = properties if isinstance(properties, dict) else {}
        original_required = node.get("required")
        required_names = (
            set(original_required) if isinstance(original_required, list) else set()
        )
        for name, property_schema in tuple(typed_properties.items()):
            if _is_free_form_object(property_schema):
                if name not in required_names:
                    del typed_properties[name]
                else:
                    raise ValueError(
                        "required free-form object fields are not supported by "
                        f"OpenAI strict Structured Outputs: {name}"
                    )
        node["additionalProperties"] = False
        node["required"] = list(typed_properties)

    node.pop("default", None)
    for value in node.values():
        _normalize_node(value)


def _is_free_form_object(value: object) -> bool:
    """Return whether a schema permits arbitrary object properties."""

    return (
        isinstance(value, dict)
        and value.get("type") == "object"
        and value.get("additionalProperties") is True
    )
