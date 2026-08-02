from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    TransparencySplitViewEvidenceConflictError,
    TransparencySplitViewEvidenceError,
    TransparencyWitnessConfigurationError,
)
from app.transparency_checkpoint import TransparencyCheckpointVerificationResult
from app.transparency_gossip import (
    create_transparency_split_view_evidence,
    export_transparency_split_view_evidence,
    load_transparency_split_view_evidence,
    verify_transparency_split_view_evidence,
)
from app.transparency_witness import (
    TRANSPARENCY_WITNESS_ID_ENV_NAME,
    TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME,
    TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME,
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


def configure_witness(monkeypatch: pytest.MonkeyPatch) -> str:
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
    monkeypatch.setenv(TRANSPARENCY_WITNESS_ID_ENV_NAME, "witness-1")
    monkeypatch.setenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME, base64.b64encode(private_bytes).decode("ascii"))
    monkeypatch.setenv(TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME, base64.b64encode(public_bytes).decode("ascii"))
    return base64.b64encode(public_bytes).decode("ascii")


def checkpoint(root: str, digest: str):
    return TransparencyCheckpointVerificationResult(1, "log-1", 3, root, "c" * 64, NOW, "log-key-1", digest)


def trust_store(public_b64: str) -> TransparencyWitnessTrustStorePayload:
    entry = TransparencyWitnessTrustEntry.model_validate(
        {
            "witness_id": "witness-1",
            "public_key_b64": public_b64,
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


def test_create_and_verify_split_view_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    public_b64 = configure_witness(monkeypatch)
    checkpoints = [checkpoint("a" * 64, "b" * 64), checkpoint("d" * 64, "e" * 64)]

    def fake_verify(**kwargs):
        return checkpoints.pop(0)

    monkeypatch.setattr("app.transparency_gossip.verify_transparency_checkpoint", fake_verify)
    evidence_path = tmp_path / "evidence.json"
    create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "checkpoint-1.json",
        conflicting_checkpoint_path=tmp_path / "checkpoint-2.json",
        output_path=evidence_path,
        detected_at=NOW,
    )

    result = verify_transparency_split_view_evidence(
        evidence_path=evidence_path,
        trust_store=trust_store(public_b64),
        verification_time=NOW,
    )

    assert result.witness_id == "witness-1"
    assert result.tree_size == 3
    assert evidence_path.stat().st_mode & 0o777 == 0o600


def test_evidence_requires_different_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    checkpoints = [checkpoint("a" * 64, "b" * 64), checkpoint("a" * 64, "e" * 64)]
    monkeypatch.setattr("app.transparency_gossip.verify_transparency_checkpoint", lambda **kwargs: checkpoints.pop(0))

    with pytest.raises(TransparencySplitViewEvidenceError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "checkpoint-1.json",
            conflicting_checkpoint_path=tmp_path / "checkpoint-2.json",
            output_path=tmp_path / "evidence.json",
            detected_at=NOW,
        )


def test_evidence_tampering_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    public_b64 = configure_witness(monkeypatch)
    checkpoints = [checkpoint("a" * 64, "b" * 64), checkpoint("d" * 64, "e" * 64)]
    monkeypatch.setattr("app.transparency_gossip.verify_transparency_checkpoint", lambda **kwargs: checkpoints.pop(0))
    evidence_path = tmp_path / "evidence.json"
    create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "checkpoint-1.json",
        conflicting_checkpoint_path=tmp_path / "checkpoint-2.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    evidence_path.write_text(evidence_path.read_text(encoding="utf-8").replace('"tree_size": 3', '"tree_size": 4'), encoding="utf-8")

    with pytest.raises(TransparencySplitViewEvidenceError):
        verify_transparency_split_view_evidence(
            evidence_path=evidence_path,
            trust_store=trust_store(public_b64),
            verification_time=NOW,
        )


def test_evidence_export_is_idempotent_but_conflict_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    checkpoints = [checkpoint("a" * 64, "b" * 64), checkpoint("d" * 64, "e" * 64)]
    monkeypatch.setattr("app.transparency_gossip.verify_transparency_checkpoint", lambda **kwargs: checkpoints.pop(0))
    evidence_path = tmp_path / "evidence.json"
    envelope = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "checkpoint-1.json",
        conflicting_checkpoint_path=tmp_path / "checkpoint-2.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    export_transparency_split_view_evidence(path=evidence_path, envelope=envelope)
    modified = load_transparency_split_view_evidence(path=evidence_path).model_copy(
        update={"signed_at": datetime(2027, 1, 1, tzinfo=UTC)}
    )

    with pytest.raises(TransparencySplitViewEvidenceConflictError):
        export_transparency_split_view_evidence(path=evidence_path, envelope=modified)



def _install_checkpoints(monkeypatch: pytest.MonkeyPatch, checkpoints: list[object]) -> None:
    pending = list(checkpoints)
    monkeypatch.setattr("app.transparency_gossip.verify_transparency_checkpoint", lambda **kwargs: pending.pop(0))


def test_same_split_view_evidence_recreation_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    public_b64 = configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    evidence_path = tmp_path / "evidence.json"
    _install_checkpoints(monkeypatch, [first, second])

    envelope = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    evidence_bytes = evidence_path.read_bytes()
    evidence_sha = hashlib.sha256(evidence_bytes).hexdigest()
    evidence_mtime = evidence_path.stat().st_mtime_ns
    detected_at = envelope.evidence.detected_at
    signed_at = envelope.signed_at
    monkeypatch.delenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME)
    _install_checkpoints(monkeypatch, [first, second])

    reused = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
    )

    assert reused == envelope
    assert evidence_path.read_bytes() == evidence_bytes
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == evidence_sha
    assert evidence_path.stat().st_mtime_ns == evidence_mtime
    assert reused.evidence.detected_at == detected_at
    assert reused.signed_at == signed_at
    assert evidence_path.stat().st_mode & 0o777 == 0o600
    verify_transparency_split_view_evidence(
        evidence_path=evidence_path,
        trust_store=trust_store(public_b64),
        verification_time=NOW,
    )


def test_reversed_checkpoint_order_reuses_same_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    evidence_path = tmp_path / "evidence.json"
    _install_checkpoints(monkeypatch, [second, first])
    envelope = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "b.json",
        conflicting_checkpoint_path=tmp_path / "a.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    before = evidence_path.read_bytes()
    mtime = evidence_path.stat().st_mtime_ns
    assert envelope.evidence.first_checkpoint_sha256 == "8" * 64
    assert envelope.evidence.second_checkpoint_sha256 == "9" * 64
    monkeypatch.delenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME)
    _install_checkpoints(monkeypatch, [first, second])

    reused = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=datetime(2026, 8, 2, 1, tzinfo=UTC),
    )

    assert reused == envelope
    assert evidence_path.read_bytes() == before
    assert evidence_path.stat().st_mtime_ns == mtime


def test_existing_different_evidence_conflicts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    other = checkpoint("6" * 64, "a" * 64)
    evidence_path = tmp_path / "evidence.json"
    _install_checkpoints(monkeypatch, [first, second])
    before = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    before_bytes = evidence_path.read_bytes()
    _install_checkpoints(monkeypatch, [first, other])

    with pytest.raises(TransparencySplitViewEvidenceConflictError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "a.json",
            conflicting_checkpoint_path=tmp_path / "c.json",
            output_path=evidence_path,
            detected_at=NOW,
        )

    assert load_transparency_split_view_evidence(path=evidence_path) == before
    assert evidence_path.read_bytes() == before_bytes


def test_existing_evidence_signature_tamper_is_not_reused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    evidence_path = tmp_path / "evidence.json"
    _install_checkpoints(monkeypatch, [first, second])
    create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace('"signature_b64": "', '"signature_b64": "AA'),
        encoding="utf-8",
    )
    _install_checkpoints(monkeypatch, [first, second])

    with pytest.raises(TransparencySplitViewEvidenceConflictError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "a.json",
            conflicting_checkpoint_path=tmp_path / "b.json",
            output_path=evidence_path,
            detected_at=NOW,
        )


def test_existing_evidence_root_hash_tamper_is_not_reused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    evidence_path = tmp_path / "evidence.json"
    _install_checkpoints(monkeypatch, [first, second])
    create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace('"first_root_hash": "d', '"first_root_hash": "a'),
        encoding="utf-8",
    )
    _install_checkpoints(monkeypatch, [first, second])

    with pytest.raises(TransparencySplitViewEvidenceConflictError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "a.json",
            conflicting_checkpoint_path=tmp_path / "b.json",
            output_path=evidence_path,
            detected_at=NOW,
        )


def test_existing_invalid_evidence_json_is_not_reused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text("{not-json", encoding="utf-8")
    _install_checkpoints(monkeypatch, [first, second])

    with pytest.raises(TransparencySplitViewEvidenceError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "a.json",
            conflicting_checkpoint_path=tmp_path / "b.json",
            output_path=evidence_path,
            detected_at=NOW,
        )


def test_new_evidence_requires_private_key_but_existing_reuse_does_not(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_witness(monkeypatch)
    first = checkpoint("d" * 64, "8" * 64)
    second = checkpoint("5" * 64, "9" * 64)
    _install_checkpoints(monkeypatch, [first, second])
    monkeypatch.delenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME)
    with pytest.raises(TransparencyWitnessConfigurationError):
        create_transparency_split_view_evidence(
            checkpoint_path=tmp_path / "a.json",
            conflicting_checkpoint_path=tmp_path / "b.json",
            output_path=tmp_path / "missing.json",
            detected_at=NOW,
        )

    configure_witness(monkeypatch)
    _install_checkpoints(monkeypatch, [first, second])
    evidence_path = tmp_path / "evidence.json"
    envelope = create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    )
    monkeypatch.delenv(TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME)
    _install_checkpoints(monkeypatch, [first, second])

    assert create_transparency_split_view_evidence(
        checkpoint_path=tmp_path / "a.json",
        conflicting_checkpoint_path=tmp_path / "b.json",
        output_path=evidence_path,
        detected_at=NOW,
    ) == envelope
