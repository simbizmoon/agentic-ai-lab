from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.exceptions import (
    ManifestTrustStateGenerationConflictError,
    ManifestTrustStatePathError,
    ManifestTrustStateRootMismatchError,
    ManifestTrustStateValidationError,
    MissingManifestTrustStateError,
    SigningKeyManifestRollbackError,
)
from app.manifest_trust_state import (
    MANIFEST_TRUST_STATE_TYPE,
    MANIFEST_TRUST_STATE_VERSION,
    ManifestTrustStateDecision,
    ManifestTrustStateMode,
    ManifestTrustStatePayload,
    apply_manifest_trust_state,
    build_manifest_trust_state,
    evaluate_manifest_trust_state,
    export_manifest_trust_state,
    format_manifest_trust_state_json,
    load_manifest_trust_state,
    manifest_trust_state_lock_path_for,
)
from app.report_integrity import is_valid_sha256_digest
from app.signature_trust import ArchiveSignatureTrustStore
from app.signing_key_manifest import (
    SigningKeyManifestVerificationResult,
    VerifiedSigningKeyManifest,
)

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
ISSUED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
ROOT_FINGERPRINT = "a" * 64
MANIFEST_DIGEST = "b" * 64
OTHER_DIGEST = "c" * 64


def verified_manifest(
    *,
    generation: int = 1,
    root_key_id: str = "root-key",
    root_key_fingerprint: str = ROOT_FINGERPRINT,
    manifest_sha256: str = MANIFEST_DIGEST,
) -> VerifiedSigningKeyManifest:
    return VerifiedSigningKeyManifest(
        result=SigningKeyManifestVerificationResult(
            manifest_version=1,
            generation=generation,
            issued_at=ISSUED_AT,
            valid_from=ISSUED_AT,
            valid_until=datetime(2027, 1, 1, tzinfo=UTC),
            root_key_id=root_key_id,
            root_key_fingerprint=root_key_fingerprint,
            active_key_id="signing-key",
            key_count=1,
            manifest_sha256=manifest_sha256,
        ),
        trust_store=ArchiveSignatureTrustStore(keys=()),
    )


def state_payload(
    *,
    generation: int = 1,
    root_key_id: str = "root-key",
    root_key_fingerprint: str = ROOT_FINGERPRINT,
    manifest_sha256: str = MANIFEST_DIGEST,
) -> ManifestTrustStatePayload:
    return ManifestTrustStatePayload(
        state_version=MANIFEST_TRUST_STATE_VERSION,
        state_type=MANIFEST_TRUST_STATE_TYPE,
        root_key_id=root_key_id,
        root_key_fingerprint=root_key_fingerprint,
        highest_generation=generation,
        manifest_sha256=manifest_sha256,
        manifest_issued_at=ISSUED_AT,
        verified_at=NOW,
    )


def test_payload_validates_and_freezes() -> None:
    state = state_payload()
    assert state.state_version == 1
    assert state.state_type == MANIFEST_TRUST_STATE_TYPE
    assert state.manifest_issued_at == ISSUED_AT
    with pytest.raises(ValidationError):
        state.highest_generation = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value",
    [
        ("root_key_id", "bad key"),
        ("root_key_fingerprint", "A" * 64),
        ("highest_generation", 0),
        ("manifest_sha256", "not-a-digest"),
        ("manifest_issued_at", datetime.fromisoformat("2026-01-01T00:00:00")),
        ("verified_at", datetime.fromisoformat("2026-01-01T00:00:00")),
    ],
)
def test_payload_rejects_invalid_fields(field: str, value: object) -> None:
    data = state_payload().model_dump()
    data[field] = value
    with pytest.raises((ManifestTrustStateValidationError, ValidationError)):
        ManifestTrustStatePayload(**data)


def test_lock_path() -> None:
    assert manifest_trust_state_lock_path_for(Path("state.json")).name == "state.json.lock"


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_manifest_trust_state(path=tmp_path / "state.json") is None


def test_export_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state" / "manifest-state.json"
    state = state_payload(generation=3)
    export_manifest_trust_state(path=path, state=state)
    loaded = load_manifest_trust_state(path=path)
    assert loaded == state
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_export_calls_file_and_directory_fsync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    original_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr("app.manifest_trust_state.os.fsync", recording_fsync)
    export_manifest_trust_state(path=tmp_path / "state.json", state=state_payload())
    assert len(calls) >= 2


def test_invalid_json_does_not_expose_raw_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"PRIVATE-STATE": true, "PRIVATE-STATE": false}', encoding="utf-8")
    with pytest.raises(ManifestTrustStateValidationError) as exc_info:
        load_manifest_trust_state(path=path)
    assert "PRIVATE-STATE" not in str(exc_info.value)


def test_build_state_from_verified_manifest() -> None:
    state = build_manifest_trust_state(
        verified_manifest=verified_manifest(generation=4),
        verified_at=NOW,
    )
    assert state.highest_generation == 4
    assert state.manifest_sha256 == MANIFEST_DIGEST
    assert state.root_key_id == "root-key"


def test_evaluate_without_stored_state_updates() -> None:
    decision = evaluate_manifest_trust_state(
        verified_manifest=verified_manifest(generation=2),
        stored_state=None,
        configured_minimum_generation=1,
    )
    assert decision.should_update is True
    assert decision.state_updated is False
    assert decision.effective_minimum_generation == 1


def test_evaluate_rejects_rollback() -> None:
    with pytest.raises(SigningKeyManifestRollbackError):
        evaluate_manifest_trust_state(
            verified_manifest=verified_manifest(generation=1),
            stored_state=state_payload(generation=2),
            configured_minimum_generation=1,
        )


def test_evaluate_rejects_same_generation_different_digest() -> None:
    with pytest.raises(ManifestTrustStateGenerationConflictError):
        evaluate_manifest_trust_state(
            verified_manifest=verified_manifest(generation=2, manifest_sha256=OTHER_DIGEST),
            stored_state=state_payload(generation=2),
            configured_minimum_generation=1,
        )


def test_evaluate_rejects_root_mismatch() -> None:
    with pytest.raises(ManifestTrustStateRootMismatchError):
        evaluate_manifest_trust_state(
            verified_manifest=verified_manifest(root_key_id="other-root"),
            stored_state=state_payload(),
            configured_minimum_generation=1,
        )


def test_evaluate_same_generation_same_digest_does_not_update() -> None:
    decision = evaluate_manifest_trust_state(
        verified_manifest=verified_manifest(generation=2),
        stored_state=state_payload(generation=2),
        configured_minimum_generation=1,
    )
    assert decision.should_update is False
    assert decision.effective_minimum_generation == 2


def test_apply_update_writes_state_and_lock(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    decision = apply_manifest_trust_state(
        verified_manifest=verified_manifest(generation=5),
        state_path=state_path,
        verified_at=NOW,
        configured_minimum_generation=1,
    )
    assert decision.state_updated is True
    assert load_manifest_trust_state(path=state_path).highest_generation == 5  # type: ignore[union-attr]
    assert manifest_trust_state_lock_path_for(state_path).exists()


def test_apply_read_only_without_path_uses_configured_minimum() -> None:
    decision = apply_manifest_trust_state(
        verified_manifest=verified_manifest(generation=2),
        state_path=None,
        verified_at=NOW,
        configured_minimum_generation=2,
        mode=ManifestTrustStateMode.READ_ONLY,
    )
    assert isinstance(decision, ManifestTrustStateDecision)
    assert decision.should_update is True
    assert decision.state_updated is False


def test_apply_update_without_path_rejects() -> None:
    with pytest.raises(ManifestTrustStatePathError):
        apply_manifest_trust_state(
            verified_manifest=verified_manifest(),
            state_path=None,
            verified_at=NOW,
        )


def test_require_existing_state_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(MissingManifestTrustStateError):
        apply_manifest_trust_state(
            verified_manifest=verified_manifest(),
            state_path=tmp_path / "state.json",
            verified_at=NOW,
            require_existing_state=True,
        )


def test_format_contains_public_digest_only() -> None:
    rendered = format_manifest_trust_state_json(state_payload())
    assert is_valid_sha256_digest(MANIFEST_DIGEST)
    assert MANIFEST_DIGEST in rendered
    assert "PRIVATE-STATE" not in rendered
