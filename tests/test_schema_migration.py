from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.audit_report import (
    AUDIT_REPORT_SCHEMA_VERSION,
    AuditReportPayload,
    validate_audit_report_json,
)
from app.exceptions import (
    InvalidMigrationRegistryError,
    InvalidSchemaVersionError,
    MissingSchemaMigrationError,
    SchemaDowngradeError,
    SchemaMigrationStepError,
    UnsupportedSchemaVersionError,
)
from app.schema_migration import (
    build_migration_path,
    extract_schema_version,
    migrate_schema_payload,
    validate_migration_registry,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PAYLOAD_FIXTURE = FIXTURE_DIR / "audit_report_v1.json"
PRIVATE_PAYLOAD = "PRIVATE-PAYLOAD"
PRIVATE_ERROR = "PRIVATE-MIGRATION-ERROR"


def base_payload(version: int = 1) -> dict[str, object]:
    return {
        "schema_version": version,
        "nested": {"items": ["alpha"]},
        "history": [],
    }


def migrate_v1_to_v2(payload: dict[str, object]) -> dict[str, object]:
    payload["schema_version"] = 2
    payload["v2"] = True
    history = payload["history"]
    assert isinstance(history, list)
    history.append("1-2")
    return payload


def migrate_v2_to_v3(payload: dict[str, object]) -> dict[str, object]:
    payload["schema_version"] = 3
    payload["v3"] = True
    history = payload["history"]
    assert isinstance(history, list)
    history.append("2-3")
    return payload


def test_extract_schema_version_accepts_version_1() -> None:
    assert extract_schema_version({"schema_version": 1}) == 1


def test_extract_schema_version_accepts_version_2() -> None:
    assert extract_schema_version({"schema_version": 2}) == 2


@pytest.mark.parametrize("payload", [None, []])
def test_extract_schema_version_rejects_non_dict(payload: object) -> None:
    with pytest.raises(InvalidSchemaVersionError):
        extract_schema_version(payload)


def test_extract_schema_version_rejects_missing_field() -> None:
    with pytest.raises(InvalidSchemaVersionError):
        extract_schema_version({})


@pytest.mark.parametrize("version", [True, "1", 1.0, 0, -1])
def test_extract_schema_version_rejects_invalid_values(version: object) -> None:
    with pytest.raises(InvalidSchemaVersionError):
        extract_schema_version({"schema_version": version})


def test_extract_schema_version_error_omits_private_payload() -> None:
    with pytest.raises(InvalidSchemaVersionError) as exc_info:
        extract_schema_version({"schema_version": PRIVATE_PAYLOAD})

    assert PRIVATE_PAYLOAD not in str(exc_info.value)


def test_validate_migration_registry_accepts_empty_registry() -> None:
    validate_migration_registry({})


def test_validate_migration_registry_accepts_single_step() -> None:
    validate_migration_registry({(1, 2): migrate_v1_to_v2})


def test_validate_migration_registry_accepts_multiple_steps() -> None:
    validate_migration_registry({(1, 2): migrate_v1_to_v2, (2, 3): migrate_v2_to_v3})


@pytest.mark.parametrize(
    "registry",
    [
        {"1-2": migrate_v1_to_v2},
        {(1, 2, 3): migrate_v1_to_v2},
        {(True, 2): migrate_v1_to_v2},
        {(1, False): migrate_v1_to_v2},
        {(0, 1): migrate_v1_to_v2},
        {(1, 0): migrate_v1_to_v2},
        {(1, 1): migrate_v1_to_v2},
        {(2, 1): migrate_v1_to_v2},
        {(1, 3): migrate_v1_to_v2},
        {(1, 2): "not-callable"},
    ],
)
def test_validate_migration_registry_rejects_invalid_registry(
    registry: object,
) -> None:
    with pytest.raises(InvalidMigrationRegistryError):
        validate_migration_registry(registry)  # type: ignore[arg-type]


def test_validate_migration_registry_does_not_mutate_original() -> None:
    registry = {(1, 2): migrate_v1_to_v2}
    before = dict(registry)

    validate_migration_registry(registry)

    assert registry == before


def test_build_migration_path_same_version_is_empty() -> None:
    assert build_migration_path(source_version=1, target_version=1) == ()


def test_build_migration_path_one_step() -> None:
    assert build_migration_path(source_version=1, target_version=2) == ((1, 2),)


def test_build_migration_path_from_1_to_4() -> None:
    assert build_migration_path(source_version=1, target_version=4) == (
        (1, 2),
        (2, 3),
        (3, 4),
    )


def test_build_migration_path_from_2_to_4() -> None:
    assert build_migration_path(source_version=2, target_version=4) == ((2, 3), (3, 4))


def test_build_migration_path_rejects_downgrade() -> None:
    with pytest.raises(SchemaDowngradeError):
        build_migration_path(source_version=2, target_version=1)


@pytest.mark.parametrize(
    ("source_version", "target_version"),
    [(True, 1), (1, False), (0, 1), (1, 0)],
)
def test_build_migration_path_rejects_invalid_versions(
    source_version: Any,
    target_version: Any,
) -> None:
    with pytest.raises(InvalidSchemaVersionError):
        build_migration_path(source_version=source_version, target_version=target_version)


def test_migrate_schema_payload_same_version_returns_equal_value() -> None:
    payload = base_payload()

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result == payload


def test_migrate_schema_payload_same_version_returns_new_object() -> None:
    payload = base_payload()

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result is not payload


def test_migrate_schema_payload_same_version_deep_copies_nested_values() -> None:
    payload = base_payload()

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result["nested"] is not payload["nested"]
    assert result["history"] is not payload["history"]


def test_migrate_schema_payload_one_step_to_v2() -> None:
    result = migrate_schema_payload(
        payload=base_payload(),
        target_version=2,
        registry={(1, 2): migrate_v1_to_v2},
    )

    assert result["schema_version"] == 2
    assert result["v2"] is True


def test_migrate_schema_payload_runs_steps_in_order() -> None:
    calls: list[str] = []

    def step_1_to_2(payload: dict[str, object]) -> dict[str, object]:
        calls.append("1-2")
        return migrate_v1_to_v2(payload)

    def step_2_to_3(payload: dict[str, object]) -> dict[str, object]:
        calls.append("2-3")
        return migrate_v2_to_v3(payload)

    result = migrate_schema_payload(
        payload=base_payload(),
        target_version=3,
        registry={(1, 2): step_1_to_2, (2, 3): step_2_to_3},
    )

    assert result["schema_version"] == 3
    assert calls == ["1-2", "2-3"]
    assert result["history"] == ["1-2", "2-3"]


def test_migrate_schema_payload_calls_each_step_once() -> None:
    calls = {"1-2": 0, "2-3": 0}

    def step_1_to_2(payload: dict[str, object]) -> dict[str, object]:
        calls["1-2"] += 1
        return migrate_v1_to_v2(payload)

    def step_2_to_3(payload: dict[str, object]) -> dict[str, object]:
        calls["2-3"] += 1
        return migrate_v2_to_v3(payload)

    migrate_schema_payload(
        payload=base_payload(),
        target_version=3,
        registry={(1, 2): step_1_to_2, (2, 3): step_2_to_3},
    )

    assert calls == {"1-2": 1, "2-3": 1}


def test_migrate_schema_payload_does_not_mutate_original_payload() -> None:
    payload = base_payload()
    before = deepcopy(payload)

    migrate_schema_payload(payload=payload, target_version=2, registry={(1, 2): migrate_v1_to_v2})

    assert payload == before


def test_migrate_schema_payload_does_not_mutate_registry() -> None:
    registry = {(1, 2): migrate_v1_to_v2}
    before = dict(registry)

    migrate_schema_payload(payload=base_payload(), target_version=2, registry=registry)

    assert registry == before


def test_migrate_schema_payload_rejects_missing_step() -> None:
    with pytest.raises(MissingSchemaMigrationError):
        migrate_schema_payload(payload=base_payload(), target_version=2, registry={})


@pytest.mark.parametrize("error", [ValueError(PRIVATE_ERROR), RuntimeError(PRIVATE_ERROR)])
def test_migrate_schema_payload_converts_step_exceptions(error: Exception) -> None:
    def broken_step(payload: dict[str, object]) -> dict[str, object]:
        raise error

    with pytest.raises(SchemaMigrationStepError) as exc_info:
        migrate_schema_payload(payload=base_payload(), target_version=2, registry={(1, 2): broken_step})

    assert exc_info.value.__cause__ is error
    assert PRIVATE_ERROR not in str(exc_info.value)


def test_migrate_schema_payload_does_not_catch_keyboard_interrupt() -> None:
    def interrupted_step(payload: dict[str, object]) -> dict[str, object]:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        migrate_schema_payload(
            payload=base_payload(),
            target_version=2,
            registry={(1, 2): interrupted_step},
        )


@pytest.mark.parametrize("result", [None, []])
def test_migrate_schema_payload_rejects_non_dict_step_result(result: object) -> None:
    def bad_step(payload: dict[str, object]) -> object:
        return result

    with pytest.raises(SchemaMigrationStepError):
        migrate_schema_payload(
            payload=base_payload(),
            target_version=2,
            registry={(1, 2): bad_step},  # type: ignore[dict-item]
        )


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"schema_version": True},
        {"schema_version": 1},
        {"schema_version": 3},
    ],
)
def test_migrate_schema_payload_rejects_invalid_step_versions(
    result: dict[str, object],
) -> None:
    def bad_step(payload: dict[str, object]) -> dict[str, object]:
        return result

    with pytest.raises(SchemaMigrationStepError):
        migrate_schema_payload(payload=base_payload(), target_version=2, registry={(1, 2): bad_step})


def test_migrate_schema_payload_stops_after_first_failed_step() -> None:
    calls: list[str] = []

    def broken_step(payload: dict[str, object]) -> dict[str, object]:
        calls.append("1-2")
        raise ValueError(PRIVATE_ERROR)

    def later_step(payload: dict[str, object]) -> dict[str, object]:
        calls.append("2-3")
        return migrate_v2_to_v3(payload)

    with pytest.raises(SchemaMigrationStepError):
        migrate_schema_payload(
            payload=base_payload(),
            target_version=3,
            registry={(1, 2): broken_step, (2, 3): later_step},
        )

    assert calls == ["1-2"]


def test_migrate_schema_payload_rejects_source_below_minimum() -> None:
    with pytest.raises(UnsupportedSchemaVersionError):
        migrate_schema_payload(
            payload=base_payload(version=1),
            target_version=2,
            registry={(1, 2): migrate_v1_to_v2},
            minimum_supported_version=2,
        )


def test_migrate_schema_payload_rejects_source_above_target() -> None:
    with pytest.raises(SchemaDowngradeError):
        migrate_schema_payload(payload=base_payload(version=2), target_version=1, registry={})


def test_migrate_schema_payload_rejects_target_below_minimum() -> None:
    with pytest.raises(InvalidSchemaVersionError):
        migrate_schema_payload(
            payload=base_payload(),
            target_version=1,
            registry={},
            minimum_supported_version=2,
        )


@pytest.mark.parametrize("minimum", [False, 0])
def test_migrate_schema_payload_rejects_invalid_minimum_version(minimum: object) -> None:
    with pytest.raises(InvalidSchemaVersionError):
        migrate_schema_payload(
            payload=base_payload(),
            target_version=1,
            registry={},
            minimum_supported_version=minimum,  # type: ignore[arg-type]
        )


def test_v1_fixture_can_be_loaded() -> None:
    assert isinstance(json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8")), dict)


def test_v1_fixture_original_payload_is_preserved() -> None:
    payload = json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))
    before = deepcopy(payload)

    migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert payload == before


def test_v1_fixture_same_version_uses_empty_registry() -> None:
    payload = json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result["schema_version"] == 1


def test_v1_fixture_same_version_result_equals_original() -> None:
    payload = json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result == payload


def test_v1_fixture_same_version_result_is_separate_object() -> None:
    payload = json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})

    assert result is not payload


def test_v1_fixture_result_validates_against_current_payload_schema() -> None:
    payload = json.loads(PAYLOAD_FIXTURE.read_text(encoding="utf-8"))

    result = migrate_schema_payload(payload=payload, target_version=1, registry={})
    validated = validate_audit_report_json(json.dumps(result))

    AuditReportPayload.model_validate(validated)


def test_audit_report_schema_version_remains_v1() -> None:
    assert AUDIT_REPORT_SCHEMA_VERSION == 1


def test_error_messages_omit_payload_registry_function_and_original_error() -> None:
    def broken_step(payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError(PRIVATE_ERROR)

    with pytest.raises(SchemaMigrationStepError) as step_error:
        migrate_schema_payload(
            payload={"schema_version": 1, "secret": PRIVATE_PAYLOAD},
            target_version=2,
            registry={(1, 2): broken_step},
        )
    assert PRIVATE_PAYLOAD not in str(step_error.value)
    assert PRIVATE_ERROR not in str(step_error.value)
    assert "broken_step" not in str(step_error.value)

    with pytest.raises(InvalidMigrationRegistryError) as registry_error:
        validate_migration_registry({(1, 2): PRIVATE_ERROR})  # type: ignore[dict-item]
    assert PRIVATE_ERROR not in str(registry_error.value)
