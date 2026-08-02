from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.report_integrity import calculate_sha256_bytes
from app.transparency_checkpoint import (
    TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM,
    TRANSPARENCY_CHECKPOINT_SIGNATURE_DOMAIN,
    TRANSPARENCY_CHECKPOINT_SIGNATURE_TYPE,
    TRANSPARENCY_CHECKPOINT_SIGNATURE_VERSION,
    TRANSPARENCY_CHECKPOINT_TYPE,
    TRANSPARENCY_CHECKPOINT_VERSION,
    TransparencyCheckpointPayload,
    TransparencyCheckpointSignaturePayload,
    canonicalize_transparency_checkpoint,
    checkpoint_signature_path_for,
    transparency_checkpoint_digest,
)
from app.transparency_gossip_bundle import (
    GOSSIP_BUNDLE_KEY_ID_ENV_NAME,
    GOSSIP_BUNDLE_PRIVATE_KEY_ENV_NAME,
    GOSSIP_BUNDLE_PUBLIC_KEY_ENV_NAME,
    GOSSIP_BUNDLE_PUBLIC_TRUST_STORE_ENV_NAME,
    TransparencyGossipBundleConflictError,
    create_transparency_gossip_bundle,
    load_gossip_bundle_signing_trust_store,
)
from app.transparency_merkle import (
    INCLUSION_PROOF_TYPE,
    TRANSPARENCY_MERKLE_VERSION,
    TransparencyInclusionProofPayload,
    calculate_transparency_merkle_root,
    export_transparency_inclusion_proof,
)
from app.transparency_offline_verifier import verify_transparency_gossip_bundle_offline
from app.transparency_witness import (
    TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
    TRANSPARENCY_WITNESS_SIGNATURE_DOMAIN,
    TRANSPARENCY_WITNESS_STATEMENT_TYPE,
    TRANSPARENCY_WITNESS_STATEMENT_VERSION,
    TransparencyWitnessStatementEnvelope,
    TransparencyWitnessStatementPayload,
    canonicalize_witness_statement,
    export_transparency_witness_statement,
)
from app.transparency_witness_trust import (
    TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
    TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
    RevokedWitnessPolicy,
    TransparencyWitnessStatus,
    TransparencyWitnessTrustEntry,
    TransparencyWitnessTrustStorePayload,
)

FIXED = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)
LOG_ID = "lesson-334-log"
LOG_KEY_ID = "lesson-334-log-key"
BUNDLE_KEY_ID = "lesson-334-bundle-key"
WITNESS_ID = "witness-a"


def _raw_private(private: Ed25519PrivateKey) -> bytes:
    return private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _raw_public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _write_model(path: Path, model) -> None:
    path.write_text(json.dumps(model.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")


def build_bundle_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    log_private = Ed25519PrivateKey.generate()
    bundle_private = Ed25519PrivateKey.generate()
    witness_private = Ed25519PrivateKey.generate()

    monkeypatch.setenv("AUDIT_REPORT_TRANSPARENCY_LOG_ID", LOG_ID)
    monkeypatch.setenv("AUDIT_REPORT_TRANSPARENCY_LOG_ED25519_PUBLIC_KEY_B64", _b64(_raw_public(log_private)))
    monkeypatch.setenv("AUDIT_REPORT_TRANSPARENCY_LOG_ED25519_KEY_ID", LOG_KEY_ID)
    monkeypatch.setenv(GOSSIP_BUNDLE_PRIVATE_KEY_ENV_NAME, _b64(_raw_private(bundle_private)))
    monkeypatch.setenv(GOSSIP_BUNDLE_PUBLIC_KEY_ENV_NAME, _b64(_raw_public(bundle_private)))
    monkeypatch.setenv(GOSSIP_BUNDLE_KEY_ID_ENV_NAME, BUNDLE_KEY_ID)

    bundle_trust_json = json.dumps(
        {"keys": [{"key_id": BUNDLE_KEY_ID, "public_key_b64": _b64(_raw_public(bundle_private))}]}
    )
    monkeypatch.setenv(GOSSIP_BUNDLE_PUBLIC_TRUST_STORE_ENV_NAME, bundle_trust_json)

    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b'{"ok":true}\n')

    entry_hash = hashlib.sha256(b"registered-artifact-entry").hexdigest()
    root_hash = calculate_transparency_merkle_root([entry_hash])
    checkpoint = TransparencyCheckpointPayload(
        checkpoint_version=TRANSPARENCY_CHECKPOINT_VERSION,
        checkpoint_type=TRANSPARENCY_CHECKPOINT_TYPE,
        log_id=LOG_ID,
        tree_size=1,
        root_hash=root_hash,
        first_sequence=1,
        last_sequence=1,
        last_entry_hash=entry_hash,
        issued_at=FIXED,
        log_signing_key_id=LOG_KEY_ID,
    )
    checkpoint_path = tmp_path / "checkpoint.json"
    _write_model(checkpoint_path, checkpoint)
    checkpoint_sha = transparency_checkpoint_digest(checkpoint)
    checkpoint_sig = TransparencyCheckpointSignaturePayload(
        signature_version=TRANSPARENCY_CHECKPOINT_SIGNATURE_VERSION,
        signature_type=TRANSPARENCY_CHECKPOINT_SIGNATURE_TYPE,
        algorithm=TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM,
        log_id=LOG_ID,
        log_signing_key_id=LOG_KEY_ID,
        checkpoint_sha256=checkpoint_sha,
        signature_b64=_b64(
            log_private.sign(
                TRANSPARENCY_CHECKPOINT_SIGNATURE_DOMAIN
                + b"\0"
                + canonicalize_transparency_checkpoint(checkpoint)
            )
        ),
        signed_at=FIXED,
    )
    _write_model(checkpoint_signature_path_for(checkpoint_path), checkpoint_sig)

    proof = TransparencyInclusionProofPayload(
        proof_version=TRANSPARENCY_MERKLE_VERSION,
        proof_type=INCLUSION_PROOF_TYPE,
        log_id=LOG_ID,
        tree_size=1,
        leaf_index=0,
        sequence=1,
        entry_hash=entry_hash,
        root_hash=root_hash,
        audit_path=(),
        issued_at=FIXED,
    )
    proof_path = tmp_path / "inclusion-proof.json"
    export_transparency_inclusion_proof(path=proof_path, proof=proof)

    witness_public_b64 = _b64(_raw_public(witness_private))
    trust_store = TransparencyWitnessTrustStorePayload(
        trust_store_version=TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
        trust_store_type=TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
        log_id=LOG_ID,
        minimum_quorum=1,
        witnesses=(
            TransparencyWitnessTrustEntry(
                witness_id=WITNESS_ID,
                public_key_b64=witness_public_b64,
                status=TransparencyWitnessStatus.ACTIVE,
                valid_from=FIXED,
                valid_until=None,
                revoked_at=None,
            ),
        ),
    )
    witness_trust_path = tmp_path / "witnesses.json"
    _write_model(witness_trust_path, trust_store)

    statement = TransparencyWitnessStatementPayload(
        statement_version=TRANSPARENCY_WITNESS_STATEMENT_VERSION,
        statement_type=TRANSPARENCY_WITNESS_STATEMENT_TYPE,
        log_id=LOG_ID,
        witness_id=WITNESS_ID,
        checkpoint_sha256=checkpoint_sha,
        tree_size=1,
        root_hash=root_hash,
        log_signing_key_id=LOG_KEY_ID,
        observed_at=FIXED,
        previous_witnessed_tree_size=None,
        previous_witnessed_root_hash=None,
        consistency_proof_sha256=None,
    )
    statement_envelope = TransparencyWitnessStatementEnvelope(
        statement=statement,
        algorithm=TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
        signature_b64=_b64(
            witness_private.sign(
                TRANSPARENCY_WITNESS_SIGNATURE_DOMAIN + b"\0" + canonicalize_witness_statement(statement)
            )
        ),
        signed_at=FIXED,
    )
    statement_path = tmp_path / "witness-a.statement.json"
    export_transparency_witness_statement(path=statement_path, envelope=statement_envelope)

    bundle_trust_path = tmp_path / "bundle-trust.json"
    bundle_trust_path.write_text(bundle_trust_json + "\n", encoding="utf-8")

    return {
        "artifact": artifact,
        "checkpoint": checkpoint_path,
        "proof": proof_path,
        "witness_trust": witness_trust_path,
        "statement": statement_path,
        "bundle_trust": bundle_trust_path,
        "bundle": tmp_path / "gossip.bundle.zip",
    }


def test_create_bundle_and_verify_offline_without_jsonl_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = build_bundle_fixture(monkeypatch, tmp_path)
    result = create_transparency_gossip_bundle(
        output_path=paths["bundle"],
        target_artifact_path=paths["artifact"],
        artifact_type="signing_key_manifest",
        artifact_identifier="signing-key-manifest:root:1",
        checkpoint_path=paths["checkpoint"],
        inclusion_proof_path=paths["proof"],
        witness_trust_store_path=paths["witness_trust"],
        witness_statement_paths=(paths["statement"],),
        required_witness_quorum=1,
        created_at=FIXED,
        environ=os.environ,
    )
    assert paths["bundle"].is_file()
    assert result.bundle_reused is False
    assert result.witness_count == 1

    trust_store = load_gossip_bundle_signing_trust_store(path=paths["bundle_trust"], environ=os.environ)
    verified = verify_transparency_gossip_bundle_offline(
        bundle_path=paths["bundle"],
        target_artifact_path=paths["artifact"],
        bundle_signing_trust_store=trust_store,
        verification_time=FIXED,
        revoked_witness_policy=RevokedWitnessPolicy.REJECT,
    )
    assert verified.bundle_id == result.bundle_id
    assert verified.artifact_sha256 == calculate_sha256_bytes(paths["artifact"].read_bytes())
    assert verified.inclusion_verified is True
    assert verified.bundle_signature_verified is True
    assert verified.quorum_satisfied is True
    assert verified.valid_witness_ids == (WITNESS_ID,)


def test_bundle_creation_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths = build_bundle_fixture(monkeypatch, tmp_path)
    kwargs = {
        "output_path": paths["bundle"],
        "target_artifact_path": paths["artifact"],
        "artifact_type": "signing_key_manifest",
        "artifact_identifier": "signing-key-manifest:root:1",
        "checkpoint_path": paths["checkpoint"],
        "inclusion_proof_path": paths["proof"],
        "witness_trust_store_path": paths["witness_trust"],
        "witness_statement_paths": (paths["statement"],),
        "required_witness_quorum": 1,
        "created_at": FIXED,
        "environ": os.environ,
    }
    first = create_transparency_gossip_bundle(**kwargs)
    before = paths["bundle"].read_bytes()
    second = create_transparency_gossip_bundle(**kwargs)
    assert second.bundle_reused is True
    assert second.bundle_id == first.bundle_id
    assert paths["bundle"].read_bytes() == before


def test_existing_different_bundle_conflicts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths = build_bundle_fixture(monkeypatch, tmp_path)
    paths["bundle"].write_bytes(b"not-a-zip")
    with pytest.raises(TransparencyGossipBundleConflictError):
        create_transparency_gossip_bundle(
            output_path=paths["bundle"],
            target_artifact_path=paths["artifact"],
            artifact_type="signing_key_manifest",
            artifact_identifier="signing-key-manifest:root:1",
            checkpoint_path=paths["checkpoint"],
            inclusion_proof_path=paths["proof"],
            witness_trust_store_path=paths["witness_trust"],
            witness_statement_paths=(paths["statement"],),
            required_witness_quorum=1,
            created_at=FIXED,
            environ=os.environ,
        )


def test_existing_bundle_with_different_artifact_type_conflicts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = build_bundle_fixture(monkeypatch, tmp_path)

    common = {
        "output_path": paths["bundle"],
        "target_artifact_path": paths["artifact"],
        "artifact_identifier": "signing-key-manifest:root:1",
        "checkpoint_path": paths["checkpoint"],
        "inclusion_proof_path": paths["proof"],
        "witness_trust_store_path": paths["witness_trust"],
        "witness_statement_paths": (paths["statement"],),
        "required_witness_quorum": 1,
        "created_at": FIXED,
        "environ": os.environ,
    }

    create_transparency_gossip_bundle(
        **common,
        artifact_type="signing_key_manifest",
    )

    with pytest.raises(TransparencyGossipBundleConflictError):
        create_transparency_gossip_bundle(
            **common,
            artifact_type="different_artifact_type",
        )
