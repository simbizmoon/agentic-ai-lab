from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.exceptions import TransparencyOfflineVerificationError
from app.transparency_gossip_bundle import (
    create_transparency_gossip_bundle,
    load_gossip_bundle_signing_trust_store,
)
from app.transparency_offline_verifier import verify_transparency_gossip_bundle_offline
from app.transparency_witness_trust import RevokedWitnessPolicy
from tests.test_transparency_gossip_bundle import FIXED, build_bundle_fixture


def _create_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
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
    return paths


def test_offline_verification_uses_bundle_without_original_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _create_bundle(monkeypatch, tmp_path)
    trust_store = load_gossip_bundle_signing_trust_store(path=paths["bundle_trust"], environ=os.environ)
    paths["checkpoint"].unlink()
    paths["proof"].unlink()
    paths["statement"].unlink()

    result = verify_transparency_gossip_bundle_offline(
        bundle_path=paths["bundle"],
        target_artifact_path=paths["artifact"],
        bundle_signing_trust_store=trust_store,
        verification_time=FIXED,
        revoked_witness_policy=RevokedWitnessPolicy.REJECT,
    )

    assert result.checkpoint_signature_verified is True
    assert result.inclusion_verified is True
    assert result.quorum_satisfied is True


def test_offline_verification_rejects_target_artifact_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _create_bundle(monkeypatch, tmp_path)
    paths["artifact"].write_bytes(b'{"ok":false}\n')
    trust_store = load_gossip_bundle_signing_trust_store(path=paths["bundle_trust"], environ=os.environ)

    with pytest.raises(TransparencyOfflineVerificationError):
        verify_transparency_gossip_bundle_offline(
            bundle_path=paths["bundle"],
            target_artifact_path=paths["artifact"],
            bundle_signing_trust_store=trust_store,
            verification_time=FIXED,
            revoked_witness_policy=RevokedWitnessPolicy.REJECT,
        )


def test_offline_local_quorum_can_be_stricter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _create_bundle(monkeypatch, tmp_path)
    trust_store = load_gossip_bundle_signing_trust_store(path=paths["bundle_trust"], environ=os.environ)

    with pytest.raises(TransparencyOfflineVerificationError):
        verify_transparency_gossip_bundle_offline(
            bundle_path=paths["bundle"],
            target_artifact_path=paths["artifact"],
            bundle_signing_trust_store=trust_store,
            verification_time=FIXED,
            local_minimum_quorum=2,
            revoked_witness_policy=RevokedWitnessPolicy.REJECT,
        )
