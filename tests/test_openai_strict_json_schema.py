"""Tests for strict OpenAI Structured Outputs schema normalization."""

from __future__ import annotations

import json

import pytest

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
    assert "metadata" not in step["required"]
    assert "metadata" not in step["properties"]
    assert "default" not in step["properties"]["tool_name"]


def test_normalization_does_not_mutate_pydantic_schema() -> None:
    original = PlanDraftOutput.model_json_schema()

    to_openai_strict_json_schema(original)

    step = original["$defs"]["PlanStepDraft"]
    assert step["properties"]["metadata"]["additionalProperties"] is True
    assert "tool_name" not in step["required"]


def test_omitted_free_form_metadata_uses_runtime_default() -> None:
    payload = {
        "reasoning_summary": "Use one bounded step.",
        "steps": [
            {
                "step_id": "step-1",
                "title": "Inspect",
                "description": "Inspect the supplied evidence.",
                "dependencies": [],
                "tool_name": None,
                "expected_output": None,
            }
        ],
        "assumptions": [],
        "warnings": [],
    }

    output = PlanDraftOutput.model_validate_json(json.dumps(payload))

    assert output.steps[0].metadata == {}


def test_required_free_form_object_is_not_silently_changed() -> None:
    schema = {
        "type": "object",
        "properties": {
            "metadata": {
                "type": "object",
                "additionalProperties": True,
            }
        },
        "required": ["metadata"],
    }

    with pytest.raises(ValueError, match="required free-form object"):
        to_openai_strict_json_schema(schema)
