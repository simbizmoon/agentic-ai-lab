"""Pure helpers for audit report schema compatibility checks."""

from __future__ import annotations

import hashlib
import json
from enum import Enum

from app.exceptions import SchemaCompatibilityError

_ANNOTATION_KEYS = {"title", "description", "$comment", "examples", "default"}


class SchemaChangeKind(str, Enum):
    INTERNAL = "internal"
    ANNOTATION_ONLY = "annotation_only"
    BREAKING = "breaking"


def normalize_json_schema(
    value: object,
) -> object:
    if isinstance(value, dict):
        return {
            key: normalize_json_schema(value[key])
            for key in sorted(value)
            if key not in _ANNOTATION_KEYS
        }
    if isinstance(value, list):
        return [normalize_json_schema(item) for item in value]
    return value


def json_schema_fingerprint(
    schema: dict[str, object],
) -> str:
    normalized = normalize_json_schema(schema)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ensure_schema_compatible(
    *,
    current_schema: dict[str, object],
    expected_schema: dict[str, object],
) -> None:
    if normalize_json_schema(current_schema) == normalize_json_schema(expected_schema):
        return
    raise SchemaCompatibilityError(
        "The audit report schema contract changed unexpectedly."
    )


def requires_schema_version_bump(
    change_kind: SchemaChangeKind,
) -> bool:
    # Public JSON payload consumers use extra="forbid", so adding optional fields is breaking.
    if change_kind is SchemaChangeKind.INTERNAL:
        return False
    if change_kind is SchemaChangeKind.ANNOTATION_ONLY:
        return False
    if change_kind is SchemaChangeKind.BREAKING:
        return True
    raise ValueError("Unsupported schema change kind")
