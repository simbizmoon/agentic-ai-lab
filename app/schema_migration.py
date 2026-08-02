"""Pure helpers for versioned schema payload migrations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy

from app.exceptions import (
    InvalidMigrationRegistryError,
    InvalidSchemaVersionError,
    MissingSchemaMigrationError,
    SchemaDowngradeError,
    SchemaMigrationStepError,
    UnsupportedSchemaVersionError,
)

MigrationKey = tuple[int, int]
MigrationFunction = Callable[[dict[str, object]], dict[str, object]]
MigrationRegistry = Mapping[MigrationKey, MigrationFunction]


def extract_schema_version(
    payload: object,
) -> int:
    if not isinstance(payload, dict):
        raise InvalidSchemaVersionError("The schema payload has an invalid version.")

    version = payload.get("schema_version")
    if not _is_valid_version(version):
        raise InvalidSchemaVersionError("The schema payload has an invalid version.")
    return version


def validate_migration_registry(
    registry: MigrationRegistry,
) -> None:
    if not isinstance(registry, Mapping):
        raise InvalidMigrationRegistryError("The schema migration registry is invalid.")

    for key, migration_function in registry.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise InvalidMigrationRegistryError("The schema migration registry is invalid.")

        source_version, target_version = key
        if not _is_valid_version(source_version) or not _is_valid_version(target_version):
            raise InvalidMigrationRegistryError("The schema migration registry is invalid.")
        if target_version != source_version + 1:
            raise InvalidMigrationRegistryError("The schema migration registry is invalid.")
        if not callable(migration_function):
            raise InvalidMigrationRegistryError("The schema migration registry is invalid.")


def build_migration_path(
    *,
    source_version: int,
    target_version: int,
) -> tuple[MigrationKey, ...]:
    _validate_version_value(source_version)
    _validate_version_value(target_version)

    if source_version > target_version:
        raise SchemaDowngradeError("Schema downgrade migrations are not supported.")
    if source_version == target_version:
        return ()

    return tuple((version, version + 1) for version in range(source_version, target_version))


def migrate_schema_payload(
    *,
    payload: dict[str, object],
    target_version: int,
    registry: MigrationRegistry,
    minimum_supported_version: int = 1,
) -> dict[str, object]:
    _validate_version_value(target_version)
    _validate_version_value(minimum_supported_version)
    if target_version < minimum_supported_version:
        raise InvalidSchemaVersionError("The schema payload has an invalid version.")

    validate_migration_registry(registry)
    source_version = extract_schema_version(payload)
    if source_version < minimum_supported_version:
        raise UnsupportedSchemaVersionError("The schema version is not supported.")
    if source_version > target_version:
        raise SchemaDowngradeError("Schema downgrade migrations are not supported.")

    current_payload = deepcopy(payload)
    path = build_migration_path(
        source_version=source_version,
        target_version=target_version,
    )
    if not path:
        return current_payload

    for migration_key in path:
        migration_function = registry.get(migration_key)
        if migration_function is None:
            raise MissingSchemaMigrationError(
                "A required schema migration step is not registered."
            )

        current_payload = _run_migration_step(
            migration_function=migration_function,
            migration_key=migration_key,
            payload=current_payload,
        )

    if extract_schema_version(current_payload) != target_version:
        raise SchemaMigrationStepError("A schema migration step produced an invalid result.")
    return current_payload


def _run_migration_step(
    *,
    migration_function: MigrationFunction,
    migration_key: MigrationKey,
    payload: dict[str, object],
) -> dict[str, object]:
    try:
        migrated_payload = migration_function(deepcopy(payload))
    except Exception as error:
        raise SchemaMigrationStepError("A schema migration step failed.") from error

    if not isinstance(migrated_payload, dict):
        raise SchemaMigrationStepError("A schema migration step produced an invalid result.")

    try:
        migrated_version = extract_schema_version(migrated_payload)
    except InvalidSchemaVersionError as error:
        raise SchemaMigrationStepError(
            "A schema migration step produced an invalid result."
        ) from error

    if migrated_version != migration_key[1]:
        raise SchemaMigrationStepError("A schema migration step produced an invalid result.")
    return migrated_payload


def _validate_version_value(value: object) -> None:
    if not _is_valid_version(value):
        raise InvalidSchemaVersionError("The schema payload has an invalid version.")


def _is_valid_version(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1
