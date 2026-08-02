from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.exceptions import (
    TransparencyLogStateExportError,
    TransparencyLogStateValidationError,
)
from app.transparency_log_state import (
    TRANSPARENCY_LOG_STATE_TYPE,
    TRANSPARENCY_LOG_STATE_VERSION,
    TransparencyLogStatePayload,
    build_transparency_log_state,
    export_transparency_log_state,
    format_transparency_log_state_json,
    load_transparency_log_state,
)

UPDATED_AT = datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
DIGEST = "a" * 64


def state_payload() -> TransparencyLogStatePayload:
    return TransparencyLogStatePayload(
        state_version=TRANSPARENCY_LOG_STATE_VERSION,
        state_type=TRANSPARENCY_LOG_STATE_TYPE,
        log_version=1,
        last_sequence=1,
        last_entry_hash=DIGEST,
        last_artifact_type="root_transition",
        last_artifact_identifier="root-transition:1:2:1",
        updated_at=UPDATED_AT,
    )


def test_state_payload_contract() -> None:
    state = state_payload()

    assert state.state_version == 1
    assert state.state_type == TRANSPARENCY_LOG_STATE_TYPE
    assert state.updated_at == UPDATED_AT


def test_state_rejects_extra_field() -> None:
    data = state_payload().model_dump(mode="json")
    data["extra"] = "blocked"

    with pytest.raises(ValidationError):
        TransparencyLogStatePayload.model_validate(data)


def test_state_rejects_invalid_digest() -> None:
    data = state_payload().model_dump(mode="json")
    data["last_entry_hash"] = "PRIVATE-DIGEST"

    with pytest.raises(ValidationError):
        TransparencyLogStatePayload.model_validate(data)


def test_load_missing_state_returns_none(tmp_path: Path) -> None:
    assert load_transparency_log_state(path=tmp_path / "state.json") is None


def test_export_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    export_transparency_log_state(path=path, state=state_payload())

    loaded = load_transparency_log_state(path=path)

    assert loaded == state_payload()
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_load_rejects_duplicate_json_key_without_raw_content(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"state_version":1,"state_version":1,"private":"PRIVATE-STATE"}',
        encoding="utf-8",
    )

    with pytest.raises(TransparencyLogStateValidationError) as exc_info:
        load_transparency_log_state(path=path)

    assert "PRIVATE-STATE" not in str(exc_info.value)


def test_build_state_accepts_enum_like_artifact_type() -> None:
    artifact_type = SimpleNamespace(value="signing_key_manifest")
    entry = SimpleNamespace(
        entry_version=1,
        sequence=2,
        entry_hash="b" * 64,
        artifact_type=artifact_type,
        artifact_identifier="signing-key-manifest:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:1",
    )

    state = build_transparency_log_state(entry=entry, updated_at=UPDATED_AT)

    assert state.last_artifact_type == "signing_key_manifest"


def test_export_error_does_not_expose_path_or_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_replace(src: object, dst: object) -> None:
        raise OSError("PRIVATE-STATE-PATH")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(TransparencyLogStateExportError) as exc_info:
        export_transparency_log_state(path=tmp_path / "PRIVATE-STATE-PATH.json", state=state_payload())

    assert "PRIVATE-STATE-PATH" not in str(exc_info.value)


def test_format_state_json_contains_public_metadata_only() -> None:
    text = format_transparency_log_state_json(state_payload())
    data = json.loads(text)

    assert data["last_sequence"] == 1
    assert "PRIVATE" not in text
