from __future__ import annotations

import base64
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    TransparencyWitnessRollbackError,
    TransparencyWitnessSignatureError,
    TransparencyWitnessSplitViewError,
    TransparencyWitnessStateError,
)
from app.transparency_checkpoint import TransparencyCheckpointVerificationResult
from app.transparency_witness import (
    TRANSPARENCY_WITNESS_ID_ENV_NAME,
    TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME,
    TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME,
    build_transparency_witness_state,
    create_transparency_witness_statement,
    export_transparency_witness_state,
    load_transparency_witness_private_key,
    load_transparency_witness_state,
    verify_transparency_witness_statement,
)
from app.transparency_witness_trust import (
    TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
    TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
    TransparencyWitnessStatus,
    TransparencyWitnessTrustEntry,
    TransparencyWitnessTrustStorePayload,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)
FUTURE = datetime(2030, 1, 1, tzinfo=UTC)


def configure_witness(monkeypatch: pytest.MonkeyPatch, witness_id: str = "witness-1") -> tuple[bytes, str]:
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
    monkeypatch.setenv(TRANSPARENCY_WITNESS_ID_ENV_NAME, witness_id)
    monkeypatch.setenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME, base64.b64encode(private_bytes).decode("ascii"))
    monkeypatch.setenv(TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME, base64.b64encode(public_bytes).decode("ascii"))
    return public_bytes, base64.b64encode(public_bytes).decode("ascii")


def checkpoint(tree_size: int = 1, root: str = "a" * 64, digest: str = "b" * 64):
    return TransparencyCheckpointVerificationResult(
        checkpoint_version=1,
        log_id="log-1",
        tree_size=tree_size,
        root_hash=root,
        last_entry_hash="c" * 64,
        issued_at=NOW,
        log_signing_key_id="log-key-1",
        checkpoint_sha256=digest,
    )


def trust_store(public_key_b64: str) -> TransparencyWitnessTrustStorePayload:
    entry = TransparencyWitnessTrustEntry.model_validate(
        {
            "witness_id": "witness-1",
            "public_key_b64": public_key_b64,
            "status": TransparencyWitnessStatus.ACTIVE,
            "valid_from": NOW,
            "valid_until": FUTURE,
            "revoked_at": None,
        }
    )
    return TransparencyWitnessTrustStorePayload(
        trust_store_version=TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
        trust_store_type=TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
        log_id="log-1",
        minimum_quorum=1,
        witnesses=(entry,),
    )


def test_create_and_verify_statement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, public_b64 = configure_witness(monkeypatch)
    cp = checkpoint()
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: cp)
    statement_path = tmp_path / "statement.json"
    state_path = tmp_path / "state.json"

    created = create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=state_path,
        observed_at=NOW,
    )
    result = verify_transparency_witness_statement(
        statement_path=statement_path,
        checkpoint=cp,
        trust_store=trust_store(public_b64),
        verification_time=NOW,
    )

    assert created.envelope.signature_b64
    assert result.witness_id == "witness-1"
    assert state_path.stat().st_mode & 0o777 == 0o600


def test_witness_private_key_repr_does_not_include_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_witness(monkeypatch)
    key = load_transparency_witness_private_key(environ=os.environ)

    assert "PRIVATE" not in repr(key)
    assert "private_key_bytes" not in repr(key)


def test_rollback_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    state_path = tmp_path / "state.json"
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=checkpoint(tree_size=2),
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: checkpoint(tree_size=1))

    with pytest.raises(TransparencyWitnessRollbackError):
        create_transparency_witness_statement(
            checkpoint_path=tmp_path / "checkpoint.json",
            output_path=tmp_path / "statement.json",
            witness_state_path=state_path,
            observed_at=NOW,
        )


def test_same_size_conflict_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    state_path = tmp_path / "state.json"
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=checkpoint(tree_size=1, root="a" * 64),
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: checkpoint(tree_size=1, root="d" * 64))

    with pytest.raises(TransparencyWitnessSplitViewError):
        create_transparency_witness_statement(
            checkpoint_path=tmp_path / "checkpoint.json",
            output_path=tmp_path / "statement.json",
            witness_state_path=state_path,
            observed_at=NOW,
        )


def test_larger_checkpoint_requires_consistency_proof(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    state_path = tmp_path / "state.json"
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=checkpoint(tree_size=1),
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: checkpoint(tree_size=2, root="d" * 64))

    with pytest.raises(TransparencyWitnessStateError):
        create_transparency_witness_statement(
            checkpoint_path=tmp_path / "checkpoint.json",
            output_path=tmp_path / "statement.json",
            witness_state_path=state_path,
            observed_at=NOW,
        )


def test_tampered_statement_signature_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, public_b64 = configure_witness(monkeypatch)
    cp = checkpoint()
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: cp)
    statement_path = tmp_path / "statement.json"
    create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=tmp_path / "state.json",
        observed_at=NOW,
    )
    text = statement_path.read_text(encoding="utf-8").replace('"tree_size": 1', '"tree_size": 2')
    statement_path.write_text(text, encoding="utf-8")

    with pytest.raises(TransparencyWitnessSignatureError):
        verify_transparency_witness_statement(
            statement_path=statement_path,
            checkpoint=cp,
            trust_store=trust_store(public_b64),
            verification_time=NOW,
        )



def test_same_checkpoint_reprocessing_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, public_b64 = configure_witness(monkeypatch)
    cp = checkpoint(tree_size=2, root="e" * 64, digest="9" * 64)
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: cp)
    statement_path = tmp_path / "statement.json"
    state_path = tmp_path / "state.json"

    first = create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=state_path,
        observed_at=NOW,
    )
    state_bytes = state_path.read_bytes()
    statement_bytes = statement_path.read_bytes()
    state_mtime = state_path.stat().st_mtime_ns
    statement_mtime = statement_path.stat().st_mtime_ns
    updated_at = load_transparency_witness_state(path=state_path).updated_at

    second = create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=state_path,
        observed_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
    )

    assert first.state_updated is True
    assert second.state_updated is False
    assert second.state.updated_at == updated_at
    assert state_path.read_bytes() == state_bytes
    assert statement_path.read_bytes() == statement_bytes
    assert state_path.stat().st_mtime_ns == state_mtime
    assert statement_path.stat().st_mtime_ns == statement_mtime
    verify_transparency_witness_statement(
        statement_path=statement_path,
        checkpoint=cp,
        trust_store=trust_store(public_b64),
        verification_time=NOW,
    )


def test_same_state_without_statement_creates_statement_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    cp = checkpoint(tree_size=2, root="e" * 64, digest="9" * 64)
    state_path = tmp_path / "state.json"
    statement_path = tmp_path / "statement.json"
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=cp,
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    state_bytes = state_path.read_bytes()
    state_mtime = state_path.stat().st_mtime_ns
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: cp)

    created = create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=state_path,
        observed_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
    )

    assert created.state_updated is False
    assert statement_path.exists()
    assert statement_path.stat().st_mode & 0o777 == 0o600
    assert state_path.read_bytes() == state_bytes
    assert state_path.stat().st_mtime_ns == state_mtime


def test_same_state_existing_conflicting_statement_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_witness(monkeypatch)
    old_checkpoint = checkpoint(tree_size=2, root="e" * 64, digest="8" * 64)
    new_checkpoint = checkpoint(tree_size=2, root="e" * 64, digest="9" * 64)
    statement_path = tmp_path / "statement.json"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: old_checkpoint)
    create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=statement_path,
        witness_state_path=tmp_path / "old-state.json",
        observed_at=NOW,
    )
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=new_checkpoint,
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    before = statement_path.read_bytes()
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: new_checkpoint)

    with pytest.raises(TransparencyWitnessSignatureError):
        create_transparency_witness_statement(
            checkpoint_path=tmp_path / "checkpoint.json",
            output_path=statement_path,
            witness_state_path=state_path,
            observed_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
        )

    assert statement_path.read_bytes() == before


def test_larger_checkpoint_updates_state_after_consistency_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_witness(monkeypatch)
    state_path = tmp_path / "state.json"
    export_transparency_witness_state(
        path=state_path,
        state=build_transparency_witness_state(
            checkpoint=checkpoint(tree_size=1),
            witness_id="witness-1",
            updated_at=NOW,
        ),
    )
    cp = checkpoint(tree_size=2, root="d" * 64, digest="9" * 64)
    monkeypatch.setattr("app.transparency_witness.verify_transparency_checkpoint", lambda **kwargs: cp)
    monkeypatch.setattr("app.transparency_witness.load_transparency_consistency_proof", lambda **kwargs: object())
    monkeypatch.setattr("app.transparency_witness.verify_checkpoint_consistency_proof", lambda **kwargs: True)
    monkeypatch.setattr("app.transparency_witness.transparency_consistency_proof_digest", lambda proof: "f" * 64)

    created = create_transparency_witness_statement(
        checkpoint_path=tmp_path / "checkpoint.json",
        output_path=tmp_path / "statement.json",
        witness_state_path=state_path,
        observed_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
        consistency_proof_path=tmp_path / "proof.json",
    )

    assert created.state_updated is True
    stored = load_transparency_witness_state(path=state_path)
    assert stored.highest_tree_size == 2
    assert stored.highest_root_hash == "d" * 64
    assert state_path.stat().st_mode & 0o777 == 0o600
