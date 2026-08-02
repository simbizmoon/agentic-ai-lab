from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    TransparencyCheckpointLogMismatchError,
    TransparencyCheckpointSignatureError,
    TransparencyConsistencyProofMismatchError,
    TransparencyInclusionProofMismatchError,
)
from app.transparency_checkpoint import (
    TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM,
    TRANSPARENCY_LOG_ID_ENV_NAME,
    TRANSPARENCY_LOG_KEY_ID_ENV_NAME,
    TRANSPARENCY_LOG_PRIVATE_KEY_ENV_NAME,
    TRANSPARENCY_LOG_PUBLIC_KEY_ENV_NAME,
    TransparencyCheckpointVerificationMode,
    checkpoint_signature_path_for,
    create_transparency_checkpoint,
    generate_checkpoint_consistency_proof,
    generate_checkpoint_inclusion_proof,
    verify_checkpoint_consistency_proof,
    verify_checkpoint_inclusion_proof,
    verify_transparency_checkpoint,
)
from app.transparency_log import (
    register_verified_artifact,
    transparency_artifact_from_verified_root_transition,
    verify_transparency_log,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)
ROOT_FP = "a" * 64
NEXT_FP = "b" * 64


def configure_key(monkeypatch: pytest.MonkeyPatch) -> None:
    private = Ed25519PrivateKey.generate()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv(TRANSPARENCY_LOG_ID_ENV_NAME, "log-1")
    monkeypatch.setenv(TRANSPARENCY_LOG_KEY_ID_ENV_NAME, "log-key-1")
    monkeypatch.setenv(TRANSPARENCY_LOG_PRIVATE_KEY_ENV_NAME, base64.b64encode(private_bytes).decode("ascii"))
    monkeypatch.setenv(TRANSPARENCY_LOG_PUBLIC_KEY_ENV_NAME, base64.b64encode(public_bytes).decode("ascii"))


def root_result(index: int):
    return SimpleNamespace(
        transition_version=1,
        transition_generation=index,
        issued_at=NOW,
        valid_from=NOW,
        valid_until=datetime(2030, 1, 1, tzinfo=UTC),
        previous_root_epoch=index,
        previous_root_key_id=f"root-{index}",
        previous_root_fingerprint=ROOT_FP,
        next_root_epoch=index + 1,
        next_root_key_id=f"root-{index + 1}",
        next_root_fingerprint=NEXT_FP,
        transition_sha256=f"{index:064x}",
    )


def build_log(tmp_path: Path, count: int = 3) -> tuple[Path, Path]:
    log_path = tmp_path / "transparency.jsonl"
    state_path = tmp_path / "transparency-state.json"
    for index in range(1, count + 1):
        register_verified_artifact(
            log_path=log_path,
            state_path=state_path,
            artifact=transparency_artifact_from_verified_root_transition(root_result(index)),
            recorded_at=NOW,
        )
    return log_path, state_path


def test_create_and_verify_checkpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=3)
    checkpoint_path = tmp_path / "checkpoint.json"

    created = create_transparency_checkpoint(
        output_path=checkpoint_path,
        log_path=log_path,
        log_state_path=state_path,
        log_id="log-1",
        issued_at=NOW,
    )
    result = verify_transparency_checkpoint(
        checkpoint_path=checkpoint_path,
        log_path=log_path,
        log_state_path=state_path,
        mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG,
    )

    assert created.signature.algorithm == TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM
    assert result.tree_size == 3
    assert result.checkpoint_sha256 == created.checkpoint_sha256
    assert checkpoint_signature_path_for(checkpoint_path).exists()


def test_checkpoint_verify_uses_public_key_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=1)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_transparency_checkpoint(output_path=checkpoint_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    monkeypatch.delenv(TRANSPARENCY_LOG_PRIVATE_KEY_ENV_NAME)

    result = verify_transparency_checkpoint(
        checkpoint_path=checkpoint_path,
        log_path=None,
        log_state_path=None,
        mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
    )

    assert result.log_id == "log-1"


def test_checkpoint_signature_tamper_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=1)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_transparency_checkpoint(output_path=checkpoint_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    checkpoint_path.write_text(checkpoint_path.read_text(encoding="utf-8").replace("log-1", "log-2"), encoding="utf-8")

    with pytest.raises(TransparencyCheckpointSignatureError):
        verify_transparency_checkpoint(checkpoint_path=checkpoint_path, log_path=None, log_state_path=None, mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY)


def test_checkpoint_log_root_mismatch_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=2)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_transparency_checkpoint(output_path=checkpoint_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    register_verified_artifact(
        log_path=log_path,
        state_path=state_path,
        artifact=transparency_artifact_from_verified_root_transition(root_result(3)),
        recorded_at=NOW,
    )

    with pytest.raises(TransparencyCheckpointLogMismatchError):
        verify_transparency_checkpoint(checkpoint_path=checkpoint_path, log_path=log_path, log_state_path=state_path, mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG)


def test_inclusion_proof_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=3)
    checkpoint_path = tmp_path / "checkpoint.json"
    create_transparency_checkpoint(output_path=checkpoint_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    checkpoint = verify_transparency_checkpoint(checkpoint_path=checkpoint_path, log_path=log_path, log_state_path=state_path, mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG)
    verification = verify_transparency_log(log_path=log_path, state_path=state_path)
    inclusion = verification.entries_by_identifier["root-transition:2:3:2"]
    proof = generate_checkpoint_inclusion_proof(checkpoint=checkpoint, log_path=log_path, log_state_path=state_path, inclusion=inclusion, issued_at=NOW)

    assert verify_checkpoint_inclusion_proof(checkpoint=checkpoint, proof=proof).sequence == 2
    bad = proof.model_copy(update={"root_hash": "f" * 64})
    with pytest.raises(TransparencyInclusionProofMismatchError):
        verify_checkpoint_inclusion_proof(checkpoint=checkpoint, proof=bad)


def test_consistency_proof_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_key(monkeypatch)
    log_path, state_path = build_log(tmp_path, count=2)
    old_path = tmp_path / "old.json"
    create_transparency_checkpoint(output_path=old_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    old = verify_transparency_checkpoint(checkpoint_path=old_path, log_path=log_path, log_state_path=state_path, mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG)
    register_verified_artifact(log_path=log_path, state_path=state_path, artifact=transparency_artifact_from_verified_root_transition(root_result(3)), recorded_at=NOW)
    new_path = tmp_path / "new.json"
    create_transparency_checkpoint(output_path=new_path, log_path=log_path, log_state_path=state_path, log_id="log-1", issued_at=NOW)
    new = verify_transparency_checkpoint(checkpoint_path=new_path, log_path=log_path, log_state_path=state_path, mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG)
    proof = generate_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=new, log_path=log_path, log_state_path=state_path, issued_at=NOW)

    assert verify_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=new, proof=proof).new_tree_size == 3
    bad = proof.model_copy(update={"new_root_hash": "f" * 64})
    with pytest.raises(TransparencyConsistencyProofMismatchError):
        verify_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=new, proof=bad)
