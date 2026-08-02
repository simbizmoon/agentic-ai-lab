from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    TransparencyWitnessEquivocationError,
    TransparencyWitnessQuorumError,
    TransparencyWitnessQuorumNotSatisfiedError,
)
from app.transparency_checkpoint import TransparencyCheckpointVerificationResult
from app.transparency_quorum import verify_transparency_witness_quorum
from app.transparency_witness import (
    TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
    TransparencyWitnessStatementEnvelope,
    TransparencyWitnessStatementPayload,
    canonicalize_witness_statement,
    export_transparency_witness_statement,
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
DOMAIN = b"agentic-ai-lab:transparency-witness-statement:ed25519:v1"


def key_pair() -> tuple[Ed25519PrivateKey, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, base64.b64encode(public).decode("ascii")


def checkpoint(digest: str = "b" * 64):
    return TransparencyCheckpointVerificationResult(1, "log-1", 3, "a" * 64, "c" * 64, NOW, "log-key-1", digest)


def write_statement(path: Path, witness_id: str, private: Ed25519PrivateKey, cp) -> None:
    statement = TransparencyWitnessStatementPayload(
        statement_version=1,
        statement_type="audit_report_transparency_witness_statement",
        log_id=cp.log_id,
        witness_id=witness_id,
        checkpoint_sha256=cp.checkpoint_sha256,
        tree_size=cp.tree_size,
        root_hash=cp.root_hash,
        log_signing_key_id=cp.log_signing_key_id,
        observed_at=NOW,
        previous_witnessed_tree_size=None,
        previous_witnessed_root_hash=None,
        consistency_proof_sha256=None,
    )
    signature = private.sign(DOMAIN + b"\0" + canonicalize_witness_statement(statement))
    envelope = TransparencyWitnessStatementEnvelope(
        statement=statement,
        algorithm=TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        signed_at=NOW,
    )
    export_transparency_witness_statement(path=path, envelope=envelope)


def store(keys: list[tuple[str, str]], quorum: int) -> TransparencyWitnessTrustStorePayload:
    entries = []
    for witness_id, public_b64 in keys:
        entries.append(
            TransparencyWitnessTrustEntry.model_validate(
                {
                    "witness_id": witness_id,
                    "public_key_b64": public_b64,
                    "status": TransparencyWitnessStatus.ACTIVE,
                    "valid_from": NOW,
                    "valid_until": FUTURE,
                    "revoked_at": None,
                }
            )
        )
    return TransparencyWitnessTrustStorePayload(
        trust_store_version=TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
        trust_store_type=TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
        log_id="log-1",
        minimum_quorum=quorum,
        witnesses=tuple(entries),
    )


def test_two_of_three_quorum_success(tmp_path: Path) -> None:
    cp = checkpoint()
    k1, p1 = key_pair()
    k2, p2 = key_pair()
    _, p3 = key_pair()
    s1 = tmp_path / "s1.json"
    s2 = tmp_path / "s2.json"
    write_statement(s1, "w1", k1, cp)
    write_statement(s2, "w2", k2, cp)

    result = verify_transparency_witness_quorum(
        checkpoint=cp,
        statement_paths=(s1, s2),
        trust_store=store([("w1", p1), ("w2", p2), ("w3", p3)], 2),
        verification_time=NOW,
    )

    assert result.quorum_satisfied is True
    assert result.valid_witness_count == 2


def test_one_of_three_quorum_fails(tmp_path: Path) -> None:
    cp = checkpoint()
    k1, p1 = key_pair()
    _, p2 = key_pair()
    s1 = tmp_path / "s1.json"
    write_statement(s1, "w1", k1, cp)

    with pytest.raises(TransparencyWitnessQuorumNotSatisfiedError):
        verify_transparency_witness_quorum(
            checkpoint=cp,
            statement_paths=(s1,),
            trust_store=store([("w1", p1), ("w2", p2)], 2),
            verification_time=NOW,
        )


def test_duplicate_statement_counts_once(tmp_path: Path) -> None:
    cp = checkpoint()
    k1, p1 = key_pair()
    _, p2 = key_pair()
    s1 = tmp_path / "s1.json"
    write_statement(s1, "w1", k1, cp)

    with pytest.raises(TransparencyWitnessQuorumNotSatisfiedError):
        verify_transparency_witness_quorum(
            checkpoint=cp,
            statement_paths=(s1, s1),
            trust_store=store([("w1", p1), ("w2", p2)], 2),
            verification_time=NOW,
        )


def test_same_witness_conflicting_statement_is_equivocation(tmp_path: Path) -> None:
    cp = checkpoint("b" * 64)
    other = checkpoint("d" * 64)
    k1, p1 = key_pair()
    s1 = tmp_path / "s1.json"
    s2 = tmp_path / "s2.json"
    write_statement(s1, "w1", k1, cp)
    write_statement(s2, "w1", k1, other)

    with pytest.raises(TransparencyWitnessEquivocationError):
        verify_transparency_witness_quorum(
            checkpoint=cp,
            statement_paths=(s1, s2),
            trust_store=store([("w1", p1)], 1),
            verification_time=NOW,
        )


def test_caller_quorum_cannot_be_lower_than_store(tmp_path: Path) -> None:
    cp = checkpoint()
    k1, p1 = key_pair()
    _, p2 = key_pair()
    s1 = tmp_path / "s1.json"
    write_statement(s1, "w1", k1, cp)

    with pytest.raises(TransparencyWitnessQuorumError):
        verify_transparency_witness_quorum(
            checkpoint=cp,
            statement_paths=(s1,),
            trust_store=store([("w1", p1), ("w2", p2)], 2),
            verification_time=NOW,
            required_quorum=1,
        )
