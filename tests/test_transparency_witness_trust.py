from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import TransparencyWitnessTrustStoreError
from app.transparency_witness_trust import (
    TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
    TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
    RevokedWitnessPolicy,
    TransparencyWitnessStatus,
    TransparencyWitnessTrustEntry,
    TransparencyWitnessTrustStorePayload,
    ensure_witness_trusted_for_verification,
    is_valid_witness_id,
    load_transparency_witness_trust_store,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)
FUTURE = datetime(2030, 1, 1, tzinfo=UTC)


def public_key_b64() -> str:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(public).decode("ascii")


def entry(witness_id: str = "witness-1", *, status: str = "active", revoked_at=None):
    return {
        "witness_id": witness_id,
        "public_key_b64": public_key_b64(),
        "status": TransparencyWitnessStatus(status),
        "valid_from": NOW,
        "valid_until": FUTURE,
        "revoked_at": revoked_at,
    }


def test_witness_id_policy() -> None:
    assert is_valid_witness_id("witness.01_a-b")
    assert not is_valid_witness_id("")
    assert not is_valid_witness_id("bad witness")
    assert not is_valid_witness_id("../bad")
    assert not is_valid_witness_id(123)


def test_trust_store_accepts_active_quorum() -> None:
    store = TransparencyWitnessTrustStorePayload(
        trust_store_version=TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
        trust_store_type=TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
        log_id="log-1",
        minimum_quorum=1,
        witnesses=(TransparencyWitnessTrustEntry.model_validate(entry()),),
    )

    assert store.get_witness("witness-1").status is TransparencyWitnessStatus.ACTIVE


def test_trust_store_rejects_duplicate_witness_id() -> None:
    first = TransparencyWitnessTrustEntry.model_validate(entry("witness-1"))
    second = TransparencyWitnessTrustEntry.model_validate(entry("witness-1"))

    with pytest.raises(ValueError):
        TransparencyWitnessTrustStorePayload(
            trust_store_version=TRANSPARENCY_WITNESS_TRUST_STORE_VERSION,
            trust_store_type=TRANSPARENCY_WITNESS_TRUST_STORE_TYPE,
            log_id="log-1",
            minimum_quorum=1,
            witnesses=(first, second),
        )


def test_load_trust_store_rejects_sensitive_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "witness-trust.json"
    path.write_text('{"PRIVATE-WITNESS-SECRET": true}', encoding="utf-8")

    with pytest.raises(TransparencyWitnessTrustStoreError) as exc_info:
        load_transparency_witness_trust_store(path=path)

    assert "PRIVATE-WITNESS-SECRET" not in str(exc_info.value)


def test_revoked_policy_rejects_by_default() -> None:
    witness = TransparencyWitnessTrustEntry.model_validate(
        entry("witness-1", status="revoked", revoked_at=datetime(2027, 1, 1, tzinfo=UTC))
    )

    with pytest.raises(TransparencyWitnessTrustStoreError):
        ensure_witness_trusted_for_verification(
            witness=witness,
            observed_at=NOW,
            verification_time=NOW,
            revoked_witness_policy=RevokedWitnessPolicy.REJECT,
            maximum_clock_skew=datetime.resolution,
        )


def test_revoked_policy_allows_pre_revocation() -> None:
    witness = TransparencyWitnessTrustEntry.model_validate(
        entry("witness-1", status="revoked", revoked_at=datetime(2027, 1, 1, tzinfo=UTC))
    )

    ensure_witness_trusted_for_verification(
        witness=witness,
        observed_at=NOW,
        verification_time=NOW,
        revoked_witness_policy=RevokedWitnessPolicy.ALLOW_PRE_REVOCATION,
        maximum_clock_skew=datetime.resolution,
    )
