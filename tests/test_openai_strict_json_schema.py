"""Tests for strict OpenAI Structured Outputs schema normalization."""

from __future__ import annotations

from app.planning.openai_strict_json_schema import to_openai_strict_json_schema
from app.schemas.planner_output import PlanDraftOutput


def _object_nodes(value: object):
    if isinstance(value, dict):
        if value.get("type") == "object" or isinstance(value.get("properties"), dict):
            yield value
        for item in value.values():
            yield from _object_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _object_nodes(item)


def test_planner_schema_closes_every_object_and_requires_every_property() -> None:
    original = PlanDraftOutput.model_json_schema()
    normalized = to_openai_strict_json_schema(original)

    for node in _object_nodes(normalized):
        properties = node.get("properties", {})
        assert node["additionalProperties"] is False
        assert node["required"] == list(properties)

    step = normalized["$defs"]["PlanStepDraft"]
    assert "dependencies" in step["required"]
    assert "tool_name" in step["required"]
    assert "expected_output" in step["required"]
    assert "metadata" in step["required"]
    assert step["properties"]["metadata"]["additionalProperties"] is False
    assert "default" not in step["properties"]["tool_name"]


def test_normalization_does_not_mutate_pydantic_schema() -> None:
    original = PlanDraftOutput.model_json_schema()

    to_openai_strict_json_schema(original)

    step = original["$defs"]["PlanStepDraft"]
    assert step["properties"]["metadata"]["additionalProperties"] is True
    assert "tool_name" not in step["required"]
