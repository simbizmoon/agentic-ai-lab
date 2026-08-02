from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from app.audit_report import (
    AUDIT_REPORT_SCHEMA_VERSION,
    AuditReportPayload,
    validate_audit_report_json,
)
from app.exceptions import SchemaCompatibilityError
from app.schema_compatibility import (
    SchemaChangeKind,
    ensure_schema_compatible,
    json_schema_fingerprint,
    normalize_json_schema,
    requires_schema_version_bump,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PAYLOAD_FIXTURE = FIXTURE_DIR / "audit_report_v1.json"
SCHEMA_FIXTURE = FIXTURE_DIR / "audit_report_schema_v1.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_normalize_keeps_scalar_value() -> None:
    assert normalize_json_schema("string") == "string"


def test_normalize_keeps_list_order() -> None:
    assert normalize_json_schema([{"b": 1}, {"a": 2}]) == [{"b": 1}, {"a": 2}]


def test_normalize_sorts_dict_keys() -> None:
    normalized = normalize_json_schema({"b": 1, "a": 2})

    assert list(normalized) == ["a", "b"]


def test_normalize_nested_schema() -> None:
    schema = {"properties": {"z": {"title": "Z", "type": "string"}}}

    assert normalize_json_schema(schema) == {"properties": {"z": {"type": "string"}}}


def test_normalize_removes_title() -> None:
    assert normalize_json_schema({"title": "Title", "type": "object"}) == {"type": "object"}


def test_normalize_removes_description() -> None:
    assert normalize_json_schema({"description": "Text", "type": "object"}) == {"type": "object"}


def test_normalize_removes_comment() -> None:
    assert normalize_json_schema({"$comment": "Text", "type": "object"}) == {"type": "object"}


def test_normalize_removes_examples() -> None:
    assert normalize_json_schema({"examples": [1], "type": "integer"}) == {"type": "integer"}


def test_normalize_removes_default() -> None:
    assert normalize_json_schema({"default": 1, "type": "integer"}) == {"type": "integer"}


def test_normalize_keeps_required() -> None:
    assert normalize_json_schema({"required": ["a"]}) == {"required": ["a"]}


def test_normalize_keeps_additional_properties() -> None:
    assert normalize_json_schema({"additionalProperties": False}) == {"additionalProperties": False}


def test_normalize_keeps_minimum_and_maximum() -> None:
    assert normalize_json_schema({"minimum": 0, "maximum": 1}) == {"maximum": 1, "minimum": 0}


def test_normalize_keeps_enum_and_const() -> None:
    assert normalize_json_schema({"enum": ["a"], "const": 1}) == {"const": 1, "enum": ["a"]}


def test_normalize_does_not_mutate_original() -> None:
    schema = {"title": "Title", "properties": {"b": {"default": 1, "type": "integer"}}}
    before = deepcopy(schema)

    normalize_json_schema(schema)

    assert schema == before


def test_fingerprint_same_schema_same_hash() -> None:
    schema = {"type": "object"}

    assert json_schema_fingerprint(schema) == json_schema_fingerprint(schema)


def test_fingerprint_ignores_dict_key_order() -> None:
    assert json_schema_fingerprint({"b": 1, "a": 2}) == json_schema_fingerprint({"a": 2, "b": 1})


def test_fingerprint_ignores_annotation_changes() -> None:
    assert json_schema_fingerprint({"title": "A", "type": "object"}) == json_schema_fingerprint(
        {"title": "B", "type": "object"}
    )


def test_fingerprint_detects_required_change() -> None:
    assert json_schema_fingerprint({"required": ["a"]}) != json_schema_fingerprint({"required": ["b"]})


def test_fingerprint_detects_type_change() -> None:
    assert json_schema_fingerprint({"type": "object"}) != json_schema_fingerprint({"type": "array"})


def test_fingerprint_detects_additional_properties_change() -> None:
    assert json_schema_fingerprint({"additionalProperties": False}) != json_schema_fingerprint(
        {"additionalProperties": True}
    )


def test_fingerprint_is_lowercase_sha256_hex() -> None:
    fingerprint = json_schema_fingerprint({"type": "object"})

    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)


def test_ensure_schema_compatible_accepts_same_schema() -> None:
    ensure_schema_compatible(current_schema={"type": "object"}, expected_schema={"type": "object"})


def test_ensure_schema_compatible_accepts_annotation_only_change() -> None:
    ensure_schema_compatible(
        current_schema={"title": "New", "type": "object"},
        expected_schema={"title": "Old", "type": "object"},
    )


def test_ensure_schema_compatible_rejects_field_deletion() -> None:
    with pytest.raises(SchemaCompatibilityError):
        ensure_schema_compatible(
            current_schema={"properties": {"a": {"type": "string"}}},
            expected_schema={"properties": {"a": {"type": "string"}, "b": {"type": "string"}}},
        )


def test_ensure_schema_compatible_rejects_required_change() -> None:
    with pytest.raises(SchemaCompatibilityError):
        ensure_schema_compatible(current_schema={"required": ["a"]}, expected_schema={"required": ["b"]})


def test_ensure_schema_compatible_rejects_type_change() -> None:
    with pytest.raises(SchemaCompatibilityError):
        ensure_schema_compatible(current_schema={"type": "array"}, expected_schema={"type": "object"})


def test_ensure_schema_compatible_rejects_additional_properties_change() -> None:
    with pytest.raises(SchemaCompatibilityError):
        ensure_schema_compatible(
            current_schema={"additionalProperties": True},
            expected_schema={"additionalProperties": False},
        )


def test_ensure_schema_compatible_error_omits_schema_content() -> None:
    with pytest.raises(SchemaCompatibilityError) as exc_info:
        ensure_schema_compatible(
            current_schema={"PRIVATE-SCHEMA-CONTENT": True},
            expected_schema={"type": "object"},
        )

    assert "PRIVATE-SCHEMA-CONTENT" not in str(exc_info.value)


def test_schema_change_kind_values() -> None:
    assert SchemaChangeKind.INTERNAL.value == "internal"
    assert SchemaChangeKind.ANNOTATION_ONLY.value == "annotation_only"
    assert SchemaChangeKind.BREAKING.value == "breaking"


def test_internal_change_does_not_require_version_bump() -> None:
    assert requires_schema_version_bump(SchemaChangeKind.INTERNAL) is False


def test_annotation_change_does_not_require_version_bump() -> None:
    assert requires_schema_version_bump(SchemaChangeKind.ANNOTATION_ONLY) is False


def test_breaking_change_requires_version_bump() -> None:
    assert requires_schema_version_bump(SchemaChangeKind.BREAKING) is True


def test_golden_payload_fixture_exists() -> None:
    assert PAYLOAD_FIXTURE.exists()


def test_golden_payload_json_loads() -> None:
    assert isinstance(load_json(PAYLOAD_FIXTURE), dict)


def test_golden_payload_validates() -> None:
    validate_audit_report_json(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))


def test_golden_payload_schema_version() -> None:
    payload = validate_audit_report_json(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    assert payload.schema_version == AUDIT_REPORT_SCHEMA_VERSION


def test_golden_payload_report_type() -> None:
    payload = validate_audit_report_json(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    assert payload.report_type == "structured_analysis_audit_report"


def test_golden_payload_model_dump_json_mode() -> None:
    payload = validate_audit_report_json(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    assert payload.model_dump(mode="json")["schema_version"] == AUDIT_REPORT_SCHEMA_VERSION


@pytest.mark.parametrize(
    "secret",
    [
        "sk-test",
        "CONFIDENTIAL",
        "PRIVATE-SUMMARY",
        "PRIVATE-KEYWORD",
        "PRIVATE-REVIEW-REASON",
        "resp_",
        "req_",
    ],
)
def test_golden_payload_omits_sensitive_strings(secret: str) -> None:
    assert secret not in PAYLOAD_FIXTURE.read_text(encoding="utf-8")


def test_golden_schema_fixture_exists() -> None:
    assert SCHEMA_FIXTURE.exists()


def test_golden_schema_json_loads_to_dict() -> None:
    assert isinstance(load_json(SCHEMA_FIXTURE), dict)


def test_golden_schema_matches_current_normalized_schema() -> None:
    expected_schema = load_json(SCHEMA_FIXTURE)

    assert normalize_json_schema(AuditReportPayload.model_json_schema()) == normalize_json_schema(expected_schema)


def test_golden_schema_fingerprint_matches_current_schema() -> None:
    expected_schema = load_json(SCHEMA_FIXTURE)

    assert json_schema_fingerprint(AuditReportPayload.model_json_schema()) == json_schema_fingerprint(expected_schema)


def test_golden_schema_top_level_type() -> None:
    schema = load_json(SCHEMA_FIXTURE)

    assert schema["type"] == "object"


def test_golden_schema_forbids_additional_properties() -> None:
    schema = load_json(SCHEMA_FIXTURE)

    assert schema["additionalProperties"] is False


def test_golden_schema_required_contract() -> None:
    schema = load_json(SCHEMA_FIXTURE)

    assert set(schema["required"]) == {
        "schema_version",
        "report_type",
        "filters",
        "summary",
        "correction",
        "recorded_usage",
        "latency",
        "failures",
        "errors_by_type",
        "recovery_actions",
        "models",
    }


def test_golden_schema_filename_and_version_are_v1() -> None:
    assert SCHEMA_FIXTURE.name == "audit_report_schema_v1.json"
    assert PAYLOAD_FIXTURE.name == "audit_report_v1.json"
    assert AUDIT_REPORT_SCHEMA_VERSION == 1
