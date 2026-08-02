from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.exceptions import (
    RootTransitionTransparencyConflictError,
    SigningKeyManifestTransparencyConflictError,
    TransparencyLogDivergenceError,
    TransparencyLogStateMismatchError,
    TransparencyLogValidationError,
    UnloggedRootTransitionError,
    UnloggedSigningKeyManifestError,
)
from app.transparency_log import (
    TRANSPARENCY_LOG_ENTRY_TYPE,
    TRANSPARENCY_LOG_ENTRY_VERSION,
    TRANSPARENCY_LOG_VERSION,
    RootTransitionLogMetadata,
    TransparencyLogEntryType,
    TransparencyLogEntryUnsignedPayload,
    TransparencyLogMode,
    calculate_transparency_entry_hash,
    canonicalize_transparency_log_unsigned_entry,
    register_verified_artifact,
    require_transparency_entry,
    transparency_artifact_from_verified_root_transition,
    transparency_artifact_from_verified_signing_key_manifest,
    transparency_log_lock_path_for,
    verify_transparency_log,
)
from app.transparency_log_state import load_transparency_log_state

RECORDED_AT = datetime(2026, 8, 2, 2, 0, tzinfo=UTC)
ISSUED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VALID_FROM = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
ROOT_FP = "a" * 64
NEXT_FP = "b" * 64
MANIFEST_SHA = "c" * 64
TRANSITION_SHA = "d" * 64


def paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "transparency.jsonl", tmp_path / "transparency-state.json"


def root_result(*, digest: str = TRANSITION_SHA):
    return SimpleNamespace(
        transition_version=1,
        transition_generation=1,
        issued_at=ISSUED_AT,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
        previous_root_epoch=1,
        previous_root_key_id="root-old",
        previous_root_fingerprint=ROOT_FP,
        next_root_epoch=2,
        next_root_key_id="root-new",
        next_root_fingerprint=NEXT_FP,
        transition_sha256=digest,
    )


def manifest_result(*, generation: int = 1, digest: str = MANIFEST_SHA, root_fp: str = ROOT_FP):
    return SimpleNamespace(
        manifest_version=1,
        generation=generation,
        issued_at=ISSUED_AT,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
        root_key_id="root-old",
        root_key_fingerprint=root_fp,
        active_key_id="signing-key",
        key_count=2,
        manifest_sha256=digest,
    )


def test_entry_type_and_mode_values() -> None:
    assert TransparencyLogEntryType.ROOT_TRANSITION.value == "root_transition"
    assert TransparencyLogEntryType.SIGNING_KEY_MANIFEST.value == "signing_key_manifest"
    assert TransparencyLogMode.REQUIRE_EXISTING.value == "require_existing"
    assert TransparencyLogMode.REGISTER_IF_MISSING.value == "register_if_missing"


def test_artifact_builders_create_public_identifiers() -> None:
    root_artifact = transparency_artifact_from_verified_root_transition(root_result())
    manifest_artifact = transparency_artifact_from_verified_signing_key_manifest(manifest_result())

    assert root_artifact.artifact_identifier == "root-transition:1:2:1"
    assert manifest_artifact.artifact_identifier == f"signing-key-manifest:{ROOT_FP}:1"
    assert "PRIVATE" not in root_artifact.artifact_identifier


def test_canonical_hash_is_stable() -> None:
    metadata = RootTransitionLogMetadata(
        previous_root_epoch=1,
        previous_root_key_id="root-old",
        previous_root_fingerprint=ROOT_FP,
        next_root_epoch=2,
        next_root_key_id="root-new",
        next_root_fingerprint=NEXT_FP,
        transition_generation=1,
        issued_at=ISSUED_AT,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
    )
    entry = TransparencyLogEntryUnsignedPayload(
        entry_version=TRANSPARENCY_LOG_ENTRY_VERSION,
        entry_type=TRANSPARENCY_LOG_ENTRY_TYPE,
        sequence=1,
        recorded_at=RECORDED_AT,
        artifact_type=TransparencyLogEntryType.ROOT_TRANSITION,
        artifact_version=1,
        artifact_identifier="root-transition:1:2:1",
        artifact_sha256=TRANSITION_SHA,
        previous_entry_hash=None,
        metadata=metadata,
    )

    first = calculate_transparency_entry_hash(entry)
    second = calculate_transparency_entry_hash(entry)

    assert first == second
    assert len(first) == 64
    assert canonicalize_transparency_log_unsigned_entry(entry).endswith(b"}")


def test_empty_log_and_state_verifies(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)

    result = verify_transparency_log(log_path=log_path, state_path=state_path)

    assert result.log_version == TRANSPARENCY_LOG_VERSION
    assert result.entry_count == 0
    assert result.last_entry_hash is None


def test_register_root_transition_creates_sequence_and_state(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_root_transition(root_result())

    result = register_verified_artifact(
        log_path=log_path,
        state_path=state_path,
        artifact=artifact,
        recorded_at=RECORDED_AT,
    )

    assert result.entry_registered is True
    assert result.inclusion.sequence == 1
    assert load_transparency_log_state(path=state_path).last_sequence == 1
    assert log_path.read_text(encoding="utf-8").count("\n") == 1
    assert oct(log_path.stat().st_mode & 0o777) == "0o600"
    assert oct(transparency_log_lock_path_for(log_path).stat().st_mode & 0o777) == "0o600"


def test_register_second_entry_links_previous_hash(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    root_artifact = transparency_artifact_from_verified_root_transition(root_result())
    manifest_artifact = transparency_artifact_from_verified_signing_key_manifest(manifest_result())

    first = register_verified_artifact(log_path=log_path, state_path=state_path, artifact=root_artifact, recorded_at=RECORDED_AT)
    second = register_verified_artifact(log_path=log_path, state_path=state_path, artifact=manifest_artifact, recorded_at=RECORDED_AT)
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert second.inclusion.sequence == 2
    assert lines[1]["previous_entry_hash"] == first.inclusion.entry_hash


def test_register_same_artifact_is_idempotent(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_root_transition(root_result())

    first = register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)
    second = register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)

    assert first.inclusion == second.inclusion
    assert second.entry_registered is False
    assert log_path.read_text(encoding="utf-8").count("\n") == 1


def test_conflicting_root_transition_is_rejected(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_root_transition(root_result())
    conflicting = transparency_artifact_from_verified_root_transition(root_result(digest="e" * 64))
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)

    with pytest.raises(RootTransitionTransparencyConflictError):
        register_verified_artifact(log_path=log_path, state_path=state_path, artifact=conflicting, recorded_at=RECORDED_AT)


def test_conflicting_signing_manifest_is_rejected(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_signing_key_manifest(manifest_result())
    conflicting = transparency_artifact_from_verified_signing_key_manifest(manifest_result(digest="e" * 64))
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)

    with pytest.raises(SigningKeyManifestTransparencyConflictError):
        register_verified_artifact(log_path=log_path, state_path=state_path, artifact=conflicting, recorded_at=RECORDED_AT)


def test_different_root_same_manifest_generation_is_allowed(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    first = transparency_artifact_from_verified_signing_key_manifest(manifest_result(root_fp=ROOT_FP))
    second = transparency_artifact_from_verified_signing_key_manifest(manifest_result(root_fp=NEXT_FP, digest="e" * 64))

    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=first, recorded_at=RECORDED_AT)
    result = register_verified_artifact(log_path=log_path, state_path=state_path, artifact=second, recorded_at=RECORDED_AT)

    assert result.inclusion.sequence == 2


def test_require_unlogged_root_transition_fails(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    verification = verify_transparency_log(log_path=log_path, state_path=state_path)

    with pytest.raises(UnloggedRootTransitionError):
        require_transparency_entry(
            verification_result=verification,
            artifact=transparency_artifact_from_verified_root_transition(root_result()),
        )


def test_require_unlogged_manifest_fails(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    verification = verify_transparency_log(log_path=log_path, state_path=state_path)

    with pytest.raises(UnloggedSigningKeyManifestError):
        require_transparency_entry(
            verification_result=verification,
            artifact=transparency_artifact_from_verified_signing_key_manifest(manifest_result()),
        )


def test_tampered_entry_is_detected_without_raw_log(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_root_transition(root_result())
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)
    text = log_path.read_text(encoding="utf-8").replace("root-new", "root-alt")
    log_path.write_text(text, encoding="utf-8")

    with pytest.raises(TransparencyLogValidationError) as exc_info:
        verify_transparency_log(log_path=log_path, state_path=state_path)

    assert "root-alt" not in str(exc_info.value)


def test_truncation_is_detected_by_state(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    first = transparency_artifact_from_verified_root_transition(root_result())
    second = transparency_artifact_from_verified_signing_key_manifest(manifest_result())
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=first, recorded_at=RECORDED_AT)
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=second, recorded_at=RECORDED_AT)
    first_line = log_path.read_text(encoding="utf-8").splitlines()[0] + "\n"
    log_path.write_text(first_line, encoding="utf-8")

    with pytest.raises(TransparencyLogStateMismatchError):
        verify_transparency_log(log_path=log_path, state_path=state_path)


def test_log_without_state_is_rejected(tmp_path: Path) -> None:
    log_path, state_path = paths(tmp_path)
    artifact = transparency_artifact_from_verified_root_transition(root_result())
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=artifact, recorded_at=RECORDED_AT)
    state_path.unlink()

    with pytest.raises(TransparencyLogDivergenceError):
        verify_transparency_log(log_path=log_path, state_path=state_path)
