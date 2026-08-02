from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    TransparencyDecisionReceiptConflictError,
    TransparencyDecisionReceiptError,
)
from app.transparency_decision_receipt import (
    DECISION_RECEIPT_KEY_ID_ENV_NAME,
    DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME,
    DECISION_RECEIPT_PUBLIC_KEY_ENV_NAME,
    build_trusted_decision_receipt,
    create_transparency_trust_decision_receipt,
    load_decision_receipt_trust_store,
    verify_transparency_trust_decision_receipt,
)
from app.transparency_gossip_bundle import (
    create_transparency_gossip_bundle,
    load_gossip_bundle_signing_trust_store,
)
from app.transparency_offline_verifier import verify_transparency_gossip_bundle_offline
from app.transparency_witness_trust import RevokedWitnessPolicy
from tests.test_transparency_gossip_bundle import FIXED, build_bundle_fixture

RECEIPT_KEY_ID = "receipt-key-1"


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


def _verified_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    paths = build_bundle_fixture(monkeypatch, tmp_path)
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
    bundle_trust = load_gossip_bundle_signing_trust_store(path=paths["bundle_trust"], environ=os.environ)
    result = verify_transparency_gossip_bundle_offline(
        bundle_path=paths["bundle"],
        target_artifact_path=paths["artifact"],
        bundle_signing_trust_store=bundle_trust,
        verification_time=FIXED,
        revoked_witness_policy=RevokedWitnessPolicy.REJECT,
    )
    return paths, result


def _configure_receipt_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    private = Ed25519PrivateKey.generate()
    public_b64 = _b64(_raw_public(private))
    monkeypatch.setenv(DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME, _b64(_raw_private(private)))
    monkeypatch.setenv(DECISION_RECEIPT_PUBLIC_KEY_ENV_NAME, public_b64)
    monkeypatch.setenv(DECISION_RECEIPT_KEY_ID_ENV_NAME, RECEIPT_KEY_ID)
    trust_path = tmp_path / "receipt-trust.json"
    trust_path.write_text(
        json.dumps({"keys": [{"key_id": RECEIPT_KEY_ID, "public_key_b64": public_b64}]}) + "\n",
        encoding="utf-8",
    )
    return trust_path


def test_trusted_receipt_can_be_verified_with_public_key_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _paths, verified = _verified_bundle(monkeypatch, tmp_path)
    trust_path = _configure_receipt_key(monkeypatch, tmp_path)
    receipt = build_trusted_decision_receipt(
        result=verified,
        policy_id="policy-1",
        verifier_version="test",
        verified_at=FIXED,
    )
    receipt_path = tmp_path / "decision.receipt.json"
    create_transparency_trust_decision_receipt(
        output_path=receipt_path,
        receipt=receipt,
        signed_at=FIXED,
        environ=os.environ,
    )
    monkeypatch.delenv(DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME)

    trust_store = load_decision_receipt_trust_store(path=trust_path, environ=os.environ)
    result = verify_transparency_trust_decision_receipt(
        receipt_path=receipt_path,
        trust_store=trust_store,
    )

    assert result.decision.value == "trusted"
    assert result.bundle_id == verified.bundle_id
    assert result.artifact_sha256 == verified.artifact_sha256


def test_receipt_creation_is_idempotent_for_same_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _paths, verified = _verified_bundle(monkeypatch, tmp_path)
    trust_path = _configure_receipt_key(monkeypatch, tmp_path)
    receipt = build_trusted_decision_receipt(
        result=verified,
        policy_id="policy-1",
        verifier_version="test",
        verified_at=FIXED,
    )
    receipt_path = tmp_path / "decision.receipt.json"
    create_transparency_trust_decision_receipt(output_path=receipt_path, receipt=receipt, signed_at=FIXED, environ=os.environ)
    before = receipt_path.read_bytes()
    trust_store = load_decision_receipt_trust_store(
        path=trust_path,
        environ=os.environ,
    )
    monkeypatch.delenv(DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME)

    create_transparency_trust_decision_receipt(
        output_path=receipt_path,
        receipt=receipt,
        signed_at=FIXED,
        trust_store=trust_store,
        environ=os.environ,
    )

    assert receipt_path.read_bytes() == before


def test_receipt_tampering_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _paths, verified = _verified_bundle(monkeypatch, tmp_path)
    trust_path = _configure_receipt_key(monkeypatch, tmp_path)
    receipt = build_trusted_decision_receipt(
        result=verified,
        policy_id="policy-1",
        verifier_version="test",
        verified_at=FIXED,
    )
    receipt_path = tmp_path / "decision.receipt.json"
    create_transparency_trust_decision_receipt(output_path=receipt_path, receipt=receipt, signed_at=FIXED, environ=os.environ)
    text = receipt_path.read_text(encoding="utf-8").replace("policy-1", "policy-2")
    receipt_path.write_text(text, encoding="utf-8")
    trust_store = load_decision_receipt_trust_store(path=trust_path, environ=os.environ)
    with pytest.raises(TransparencyDecisionReceiptError):
        verify_transparency_trust_decision_receipt(receipt_path=receipt_path, trust_store=trust_store)


def test_existing_different_receipt_conflicts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _paths, verified = _verified_bundle(monkeypatch, tmp_path)
    _configure_receipt_key(monkeypatch, tmp_path)
    receipt_path = tmp_path / "decision.receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    receipt = build_trusted_decision_receipt(
        result=verified,
        policy_id="policy-1",
        verifier_version="test",
        verified_at=FIXED,
    )
    with pytest.raises(TransparencyDecisionReceiptConflictError):
        create_transparency_trust_decision_receipt(output_path=receipt_path, receipt=receipt, signed_at=FIXED, environ=os.environ)
