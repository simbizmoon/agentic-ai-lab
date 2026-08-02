"""Offline verification for signed transparency gossip bundles."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from app.exceptions import TransparencyOfflineVerificationError
from app.report_integrity import calculate_sha256_bytes
from app.transparency_checkpoint import (
    TransparencyCheckpointPayload,
    TransparencyCheckpointSignaturePayload,
    TransparencyCheckpointVerificationResult,
    transparency_checkpoint_digest,
    verify_checkpoint_inclusion_proof,
)
from app.transparency_gossip_bundle import (
    ARTIFACT_BINDING_MEMBER,
    CHECKPOINT_MEMBER,
    CHECKPOINT_SIGNATURE_MEMBER,
    INCLUSION_PROOF_MEMBER,
    WITNESS_TRUST_STORE_MEMBER,
    GossipBundleSigningTrustStore,
    load_artifact_binding_from_bytes,
    load_transparency_gossip_bundle,
    validate_artifact_binding,
    verify_gossip_bundle_manifest_signature,
)
from app.transparency_merkle import (
    TransparencyInclusionProofPayload,
    transparency_inclusion_proof_digest,
)
from app.transparency_witness import (
    MAX_WITNESS_CLOCK_SKEW,
    TransparencyWitnessStatementEnvelope,
    _statement_message,  # type: ignore[attr-defined]
)
from app.transparency_witness_trust import (
    RevokedWitnessPolicy,
    TransparencyWitnessTrustStorePayload,
    ensure_witness_trusted_for_verification,
)

_MESSAGE = "The transparency gossip bundle could not be verified offline safely."


@dataclass(frozen=True)
class TransparencyOfflineVerificationResult:
    bundle_id: str
    bundle_sha256: str
    artifact_identifier: str
    artifact_sha256: str
    log_id: str
    checkpoint_sha256: str
    tree_size: int
    root_hash: str
    required_witness_quorum: int
    valid_witness_count: int
    valid_witness_ids: tuple[str, ...]
    inclusion_verified: bool
    checkpoint_signature_verified: bool
    bundle_signature_verified: bool
    quorum_satisfied: bool


def verify_transparency_gossip_bundle_offline(
    *,
    bundle_path: Path,
    target_artifact_path: Path,
    bundle_signing_trust_store: GossipBundleSigningTrustStore,
    verification_time: datetime,
    local_minimum_quorum: int | None = None,
    revoked_witness_policy: RevokedWitnessPolicy = RevokedWitnessPolicy.REJECT,
) -> TransparencyOfflineVerificationResult:
    try:
        loaded = load_transparency_gossip_bundle(path=bundle_path)
        verify_gossip_bundle_manifest_signature(loaded=loaded, trust_store=bundle_signing_trust_store)
        manifest = loaded.manifest
        members = loaded.members
        artifact_sha256 = hashlib.sha256(target_artifact_path.read_bytes()).hexdigest()
        if artifact_sha256 != manifest.artifact_sha256:
            raise TransparencyOfflineVerificationError(_MESSAGE)
        checkpoint = TransparencyCheckpointPayload.model_validate_json(members[CHECKPOINT_MEMBER].decode("utf-8"))
        checkpoint_signature = TransparencyCheckpointSignaturePayload.model_validate_json(
            members[CHECKPOINT_SIGNATURE_MEMBER].decode("utf-8")
        )
        checkpoint_sha256 = transparency_checkpoint_digest(checkpoint)
        if (
            checkpoint_sha256 != manifest.checkpoint_sha256
            or checkpoint_signature.checkpoint_sha256 != checkpoint_sha256
            or calculate_sha256_bytes(members[CHECKPOINT_SIGNATURE_MEMBER]) != manifest.checkpoint_signature_sha256
        ):
            raise TransparencyOfflineVerificationError(_MESSAGE)
        checkpoint_result = TransparencyCheckpointVerificationResult(
            checkpoint_version=checkpoint.checkpoint_version,
            log_id=checkpoint.log_id,
            tree_size=checkpoint.tree_size,
            root_hash=checkpoint.root_hash,
            last_entry_hash=checkpoint.last_entry_hash,
            issued_at=checkpoint.issued_at,
            log_signing_key_id=checkpoint.log_signing_key_id,
            checkpoint_sha256=checkpoint_sha256,
        )
        proof = TransparencyInclusionProofPayload.model_validate_json(members[INCLUSION_PROOF_MEMBER].decode("utf-8"))
        inclusion = verify_checkpoint_inclusion_proof(checkpoint=checkpoint_result, proof=proof)
        if transparency_inclusion_proof_digest(proof) != manifest.inclusion_proof_sha256:
            raise TransparencyOfflineVerificationError(_MESSAGE)
        binding = load_artifact_binding_from_bytes(members[ARTIFACT_BINDING_MEMBER])
        validate_artifact_binding(
            binding=binding,
            manifest=manifest,
            inclusion_entry_hash=inclusion.entry_hash,
            inclusion_sequence=inclusion.sequence,
        )
        trust_store = TransparencyWitnessTrustStorePayload.model_validate_json(
            members[WITNESS_TRUST_STORE_MEMBER].decode("utf-8")
        )
        if calculate_sha256_bytes(members[WITNESS_TRUST_STORE_MEMBER]) != manifest.witness_trust_store_sha256:
            raise TransparencyOfflineVerificationError(_MESSAGE)
        required_quorum = max(manifest.required_witness_quorum, trust_store.minimum_quorum)
        if local_minimum_quorum is not None:
            if isinstance(local_minimum_quorum, bool) or local_minimum_quorum < trust_store.minimum_quorum:
                raise TransparencyOfflineVerificationError(_MESSAGE)
            required_quorum = max(required_quorum, local_minimum_quorum)
        valid_ids = _verify_witness_members(
            members=members,
            manifest_statement_hashes=manifest.witness_statement_sha256s,
            checkpoint=checkpoint_result,
            trust_store=trust_store,
            verification_time=verification_time,
            revoked_witness_policy=revoked_witness_policy,
        )
        if len(valid_ids) < required_quorum:
            raise TransparencyOfflineVerificationError(_MESSAGE)
        return TransparencyOfflineVerificationResult(
            bundle_id=manifest.bundle_id,
            bundle_sha256=loaded.bundle_sha256,
            artifact_identifier=manifest.artifact_identifier,
            artifact_sha256=manifest.artifact_sha256,
            log_id=manifest.log_id,
            checkpoint_sha256=manifest.checkpoint_sha256,
            tree_size=checkpoint.tree_size,
            root_hash=checkpoint.root_hash,
            required_witness_quorum=required_quorum,
            valid_witness_count=len(valid_ids),
            valid_witness_ids=valid_ids,
            inclusion_verified=True,
            checkpoint_signature_verified=True,
            bundle_signature_verified=True,
            quorum_satisfied=True,
        )
    except TransparencyOfflineVerificationError:
        raise
    except (OSError, UnicodeDecodeError, ValidationError, ValueError, KeyError) as error:
        raise TransparencyOfflineVerificationError(_MESSAGE) from error


def _verify_witness_members(
    *,
    members: dict[str, bytes],
    manifest_statement_hashes: tuple[str, ...],
    checkpoint: TransparencyCheckpointVerificationResult,
    trust_store: TransparencyWitnessTrustStorePayload,
    verification_time: datetime,
    revoked_witness_policy: RevokedWitnessPolicy,
) -> tuple[str, ...]:
    if trust_store.log_id != checkpoint.log_id:
        raise TransparencyOfflineVerificationError(_MESSAGE)
    statement_items = [(name, data) for name, data in members.items() if name.startswith("witnesses/")]
    statement_hashes = tuple(sorted(calculate_sha256_bytes(data) for _, data in statement_items))
    if statement_hashes != tuple(sorted(manifest_statement_hashes)):
        raise TransparencyOfflineVerificationError(_MESSAGE)
    valid: dict[str, TransparencyWitnessStatementEnvelope] = {}
    for _, data in statement_items:
        envelope = TransparencyWitnessStatementEnvelope.model_validate_json(data.decode("utf-8"))
        statement = envelope.statement
        if (
            statement.log_id != checkpoint.log_id
            or statement.checkpoint_sha256 != checkpoint.checkpoint_sha256
            or statement.tree_size != checkpoint.tree_size
            or statement.root_hash != checkpoint.root_hash
            or statement.log_signing_key_id != checkpoint.log_signing_key_id
        ):
            raise TransparencyOfflineVerificationError(_MESSAGE)
        existing = valid.get(statement.witness_id)
        if existing is not None:
            continue
        witness = trust_store.get_witness(statement.witness_id)
        ensure_witness_trusted_for_verification(
            witness=witness,
            observed_at=statement.observed_at,
            verification_time=verification_time,
            revoked_witness_policy=revoked_witness_policy,
            maximum_clock_skew=MAX_WITNESS_CLOCK_SKEW,
        )
        public_key = Ed25519PublicKey.from_public_bytes(witness.public_key_bytes())
        try:
            public_key.verify(
                base64.b64decode(envelope.signature_b64.encode("ascii"), validate=True),
                _statement_message(statement),
            )
        except InvalidSignature as error:
            raise TransparencyOfflineVerificationError(_MESSAGE) from error
        valid[statement.witness_id] = envelope
    return tuple(sorted(valid))
