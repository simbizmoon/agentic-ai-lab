"""Signed ZIP bundles for offline transparency gossip verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal
from zipfile import ZIP_DEFLATED, BadZipFile, LargeZipFile, ZipFile, ZipInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.exceptions import (
    TransparencyArtifactBindingError,
    TransparencyGossipBundleConfigurationError,
    TransparencyGossipBundleConflictError,
    TransparencyGossipBundleSignatureError,
    TransparencyGossipBundleStructureError,
)
from app.report_archive import (
    COMPRESSION_RATIO_MINIMUM_SIZE,
    MAX_ARCHIVE_COMPRESSION_RATIO,
    ZIP_MEMBER_MODE,
    ZIP_MEMBER_TIMESTAMP,
)
from app.report_integrity import calculate_sha256_bytes, is_valid_sha256_digest
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationMode,
    checkpoint_signature_path_for,
    verify_checkpoint_inclusion_proof,
    verify_transparency_checkpoint,
)
from app.transparency_merkle import (
    load_transparency_consistency_proof,
    load_transparency_inclusion_proof,
    transparency_consistency_proof_digest,
    transparency_inclusion_proof_digest,
)
from app.transparency_quorum import verify_transparency_witness_quorum
from app.transparency_witness import load_transparency_witness_statement
from app.transparency_witness_trust import (
    RevokedWitnessPolicy,
    is_valid_witness_id,
    load_transparency_witness_trust_store,
    normalize_aware_datetime,
)

TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_VERSION = 1
TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_TYPE = "audit_report_transparency_gossip_bundle_manifest"
TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_DOMAIN = (
    b"agentic-ai-lab:transparency-gossip-bundle-manifest:ed25519:v1"
)
TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_VERSION = 1
TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_TYPE = "audit_report_transparency_gossip_bundle_manifest_signature"
TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_ALGORITHM = "ed25519-gossip-bundle-v1"

GOSSIP_BUNDLE_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_GOSSIP_BUNDLE_ED25519_PRIVATE_KEY_B64"
GOSSIP_BUNDLE_PUBLIC_KEY_ENV_NAME = "AUDIT_REPORT_GOSSIP_BUNDLE_ED25519_PUBLIC_KEY_B64"
GOSSIP_BUNDLE_KEY_ID_ENV_NAME = "AUDIT_REPORT_GOSSIP_BUNDLE_ED25519_KEY_ID"
GOSSIP_BUNDLE_PUBLIC_TRUST_STORE_ENV_NAME = "AUDIT_REPORT_GOSSIP_BUNDLE_PUBLIC_TRUST_STORE_JSON"
RAW_ED25519_PRIVATE_KEY_BYTES = 32
RAW_ED25519_PUBLIC_KEY_BYTES = 32
RAW_ED25519_SIGNATURE_BYTES = 64

TRANSPARENCY_ARTIFACT_BINDING_VERSION = 1
TRANSPARENCY_ARTIFACT_BINDING_TYPE = "audit_report_transparency_artifact_binding"
GOSSIP_BUNDLE_FILE_MODE = 0o600
MAX_GOSSIP_BUNDLE_BYTES = 20 * 1024 * 1024
MAX_GOSSIP_BUNDLE_MEMBER_BYTES = 10 * 1024 * 1024
MAX_GOSSIP_BUNDLE_TOTAL_BYTES = 20 * 1024 * 1024
MAX_GOSSIP_BUNDLE_MEMBERS = 128

MANIFEST_MEMBER = "gossip-manifest.json"
MANIFEST_SIGNATURE_MEMBER = "gossip-manifest.json.sig"
CHECKPOINT_MEMBER = "checkpoint/checkpoint.json"
CHECKPOINT_SIGNATURE_MEMBER = "checkpoint/checkpoint.json.sig"
INCLUSION_PROOF_MEMBER = "proofs/inclusion-proof.json"
CONSISTENCY_PROOF_MEMBER = "proofs/consistency-proof.json"
WITNESS_TRUST_STORE_MEMBER = "trust/witness-trust-store.json"
ARTIFACT_BINDING_MEMBER = "artifact/artifact-binding.json"

_MESSAGE = "The transparency gossip bundle is invalid."
_CONFIG_MESSAGE = "The transparency gossip bundle signing key is not configured safely."
_CONFLICT_MESSAGE = "The transparency gossip bundle conflicts with an existing file."


class _BundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyGossipBundleManifestPayload(_BundleModel):
    manifest_version: Literal[TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_VERSION]
    manifest_type: Literal[TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_TYPE]
    bundle_id: str
    log_id: str = Field(min_length=1, max_length=128)
    checkpoint_sha256: str
    checkpoint_signature_sha256: str
    artifact_type: str = Field(min_length=1, max_length=128)
    artifact_identifier: str = Field(min_length=1, max_length=256)
    artifact_sha256: str
    inclusion_proof_sha256: str
    consistency_proof_sha256: str | None
    witness_trust_store_sha256: str
    witness_statement_sha256s: tuple[str, ...]
    required_witness_quorum: int = Field(ge=1)
    created_at: datetime
    bundle_signing_key_id: str = Field(min_length=1, max_length=128)

    @field_validator(
        "bundle_id",
        "checkpoint_sha256",
        "checkpoint_signature_sha256",
        "artifact_sha256",
        "inclusion_proof_sha256",
        "consistency_proof_sha256",
        "witness_trust_store_sha256",
    )
    @classmethod
    def _validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("witness_statement_sha256s")
    @classmethod
    def _validate_statement_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not is_valid_sha256_digest(item) for item in value):
            raise ValueError("invalid witness digest")
        return value

    @field_validator("required_witness_quorum")
    @classmethod
    def _validate_quorum(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("invalid quorum")
        return value

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_bundle_id(self) -> TransparencyGossipBundleManifestPayload:
        if self.bundle_id != calculate_gossip_bundle_id(
            log_id=self.log_id,
            checkpoint_sha256=self.checkpoint_sha256,
            artifact_type=self.artifact_type,
            artifact_identifier=self.artifact_identifier,
            artifact_sha256=self.artifact_sha256,
            inclusion_proof_sha256=self.inclusion_proof_sha256,
            witness_statement_sha256s=self.witness_statement_sha256s,
            required_witness_quorum=self.required_witness_quorum,
        ):
            raise ValueError("bundle id mismatch")
        return self


class TransparencyGossipBundleManifestSignaturePayload(_BundleModel):
    signature_version: Literal[TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_VERSION]
    signature_type: Literal[TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_TYPE]
    algorithm: Literal[TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_ALGORITHM]
    bundle_signing_key_id: str = Field(min_length=1, max_length=128)
    bundle_id: str
    manifest_sha256: str
    signature_b64: str
    signed_at: datetime

    @field_validator("bundle_id", "manifest_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        _decode_b64(value, expected_size=RAW_ED25519_SIGNATURE_BYTES)
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


class TransparencyArtifactBindingPayload(_BundleModel):
    binding_version: Literal[TRANSPARENCY_ARTIFACT_BINDING_VERSION]
    binding_type: Literal[TRANSPARENCY_ARTIFACT_BINDING_TYPE]
    artifact_type: str = Field(min_length=1, max_length=128)
    artifact_identifier: str = Field(min_length=1, max_length=256)
    artifact_sha256: str
    transparency_entry_sequence: int = Field(ge=1)
    transparency_entry_hash: str
    checkpoint_sha256: str
    inclusion_proof_sha256: str

    @field_validator("artifact_sha256", "transparency_entry_hash", "checkpoint_sha256", "inclusion_proof_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("transparency_entry_sequence")
    @classmethod
    def _validate_sequence(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("invalid sequence")
        return value


@dataclass(frozen=True)
class GossipBundleSigningPrivateKey:
    key_id: str
    private_key_bytes: bytes
    public_key_bytes: bytes

    def __repr__(self) -> str:
        return f"GossipBundleSigningPrivateKey(key_id={self.key_id!r})"


@dataclass(frozen=True)
class GossipBundleSigningTrustStore:
    keys: dict[str, bytes]

    def get_public_key(self, key_id: str) -> bytes:
        try:
            return self.keys[key_id]
        except KeyError as error:
            raise TransparencyGossipBundleSignatureError(_MESSAGE) from error


@dataclass(frozen=True)
class TransparencyGossipBundleCreationResult:
    bundle_id: str
    bundle_sha256: str
    member_count: int
    artifact_identifier: str
    artifact_sha256: str
    checkpoint_sha256: str
    required_witness_quorum: int
    witness_count: int
    bundle_reused: bool


@dataclass(frozen=True)
class LoadedGossipBundle:
    bundle_path: Path
    bundle_sha256: str
    members: dict[str, bytes]
    manifest: TransparencyGossipBundleManifestPayload
    manifest_signature: TransparencyGossipBundleManifestSignaturePayload


def calculate_gossip_bundle_id(
    *,
    log_id: str,
    checkpoint_sha256: str,
    artifact_type: str,
    artifact_identifier: str,
    artifact_sha256: str,
    inclusion_proof_sha256: str,
    witness_statement_sha256s: tuple[str, ...],
    required_witness_quorum: int,
) -> str:
    payload = {
        "artifact_identifier": artifact_identifier,
        "artifact_sha256": artifact_sha256,
        "artifact_type": artifact_type,
        "checkpoint_sha256": checkpoint_sha256,
        "inclusion_proof_sha256": inclusion_proof_sha256,
        "log_id": log_id,
        "required_witness_quorum": required_witness_quorum,
        "witness_statement_sha256s": tuple(sorted(witness_statement_sha256s)),
    }
    return hashlib.sha256(_canonicalize_mapping(payload)).hexdigest()


def canonicalize_gossip_bundle_manifest(manifest: TransparencyGossipBundleManifestPayload) -> bytes:
    return _canonicalize_model(manifest)


def gossip_bundle_manifest_digest(manifest: TransparencyGossipBundleManifestPayload) -> str:
    return hashlib.sha256(canonicalize_gossip_bundle_manifest(manifest)).hexdigest()


def load_gossip_bundle_signing_private_key(
    *, environ: dict[str, str] | os._Environ[str] = os.environ
) -> GossipBundleSigningPrivateKey:
    private_bytes = _env_b64(environ, GOSSIP_BUNDLE_PRIVATE_KEY_ENV_NAME, RAW_ED25519_PRIVATE_KEY_BYTES)
    public_bytes = _env_b64(environ, GOSSIP_BUNDLE_PUBLIC_KEY_ENV_NAME, RAW_ED25519_PUBLIC_KEY_BYTES)
    key_id = _env_text(environ, GOSSIP_BUNDLE_KEY_ID_ENV_NAME)
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    derived = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived != public_bytes:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    return GossipBundleSigningPrivateKey(key_id=key_id, private_key_bytes=private_bytes, public_key_bytes=public_bytes)


def load_gossip_bundle_signing_trust_store(
    *, path: Path | None = None, environ: dict[str, str] | os._Environ[str] = os.environ
) -> GossipBundleSigningTrustStore:
    if path is not None:
        raw = _load_json_file(path=path, max_bytes=256 * 1024)
    else:
        value = environ.get(GOSSIP_BUNDLE_PUBLIC_TRUST_STORE_ENV_NAME)  # type: ignore[attr-defined]
        if not value:
            public_bytes = _env_b64(environ, GOSSIP_BUNDLE_PUBLIC_KEY_ENV_NAME, RAW_ED25519_PUBLIC_KEY_BYTES)
            return GossipBundleSigningTrustStore(keys={_env_text(environ, GOSSIP_BUNDLE_KEY_ID_ENV_NAME): public_bytes})
        raw = _loads_no_duplicate_keys(value)
    if not isinstance(raw, dict) or set(raw) != {"keys"} or not isinstance(raw["keys"], list):
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    keys: dict[str, bytes] = {}
    for item in raw["keys"]:
        if not isinstance(item, dict) or set(item) != {"key_id", "public_key_b64"}:
            raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
        key_id = item["key_id"]
        if not isinstance(key_id, str) or not key_id:
            raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
        public_bytes = _decode_b64(item["public_key_b64"], expected_size=RAW_ED25519_PUBLIC_KEY_BYTES)
        if key_id in keys:
            raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
        Ed25519PublicKey.from_public_bytes(public_bytes)
        keys[key_id] = public_bytes
    return GossipBundleSigningTrustStore(keys=keys)


def build_artifact_binding(
    *,
    artifact_type: str,
    artifact_identifier: str,
    artifact_sha256: str,
    checkpoint_sha256: str,
    inclusion_proof_sha256: str,
    transparency_entry_sequence: int,
    transparency_entry_hash: str,
) -> TransparencyArtifactBindingPayload:
    return TransparencyArtifactBindingPayload(
        binding_version=TRANSPARENCY_ARTIFACT_BINDING_VERSION,
        binding_type=TRANSPARENCY_ARTIFACT_BINDING_TYPE,
        artifact_type=artifact_type,
        artifact_identifier=artifact_identifier,
        artifact_sha256=artifact_sha256,
        transparency_entry_sequence=transparency_entry_sequence,
        transparency_entry_hash=transparency_entry_hash,
        checkpoint_sha256=checkpoint_sha256,
        inclusion_proof_sha256=inclusion_proof_sha256,
    )


def create_transparency_gossip_bundle(
    *,
    output_path: Path,
    target_artifact_path: Path,
    checkpoint_path: Path,
    inclusion_proof_path: Path,
    witness_trust_store_path: Path,
    witness_statement_paths: tuple[Path, ...] | list[Path],
    artifact_type: str,
    artifact_identifier: str,
    created_at: datetime,
    consistency_proof_path: Path | None = None,
    required_witness_quorum: int | None = None,
    environ: dict[str, str] | os._Environ[str] = os.environ,
) -> TransparencyGossipBundleCreationResult:
    artifact_sha256 = _sha256_file(target_artifact_path)
    checkpoint = verify_transparency_checkpoint(
        checkpoint_path=checkpoint_path,
        log_path=None,
        log_state_path=None,
        mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
    )
    inclusion_proof = load_transparency_inclusion_proof(path=inclusion_proof_path)
    inclusion = verify_checkpoint_inclusion_proof(checkpoint=checkpoint, proof=inclusion_proof)
    inclusion_digest = transparency_inclusion_proof_digest(inclusion_proof)
    binding = build_artifact_binding(
        artifact_type=artifact_type,
        artifact_identifier=artifact_identifier,
        artifact_sha256=artifact_sha256,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        inclusion_proof_sha256=inclusion_digest,
        transparency_entry_sequence=inclusion.sequence,
        transparency_entry_hash=inclusion.entry_hash,
    )
    witness_trust = load_transparency_witness_trust_store(path=witness_trust_store_path)
    quorum = verify_transparency_witness_quorum(
        checkpoint=checkpoint,
        statement_paths=witness_statement_paths,
        trust_store=witness_trust,
        verification_time=created_at,
        required_quorum=required_witness_quorum,
        revoked_witness_policy=RevokedWitnessPolicy.REJECT,
    )
    checkpoint_bytes = checkpoint_path.read_bytes()
    checkpoint_sig_bytes = checkpoint_signature_path_for(checkpoint_path).read_bytes()
    inclusion_bytes = inclusion_proof_path.read_bytes()
    trust_bytes = witness_trust_store_path.read_bytes()
    witness_members: list[tuple[str, bytes]] = []
    for statement_path in witness_statement_paths:
        envelope = load_transparency_witness_statement(path=statement_path)
        witness_members.append((_witness_member_name(envelope.statement.witness_id), statement_path.read_bytes()))
    witness_members.sort(key=lambda item: item[0])
    consistency_digest = None
    consistency_bytes = None
    if consistency_proof_path is not None:
        proof = load_transparency_consistency_proof(path=consistency_proof_path)
        consistency_digest = transparency_consistency_proof_digest(proof)
        consistency_bytes = consistency_proof_path.read_bytes()
    statement_digests = tuple(
        calculate_sha256_bytes(data)
        for _, data in witness_members
    )

    if output_path.exists():
        trust_store = load_gossip_bundle_signing_trust_store(environ=environ)
        try:
            loaded = load_transparency_gossip_bundle(path=output_path)
            verify_gossip_bundle_manifest_signature(
                loaded=loaded,
                trust_store=trust_store,
            )
        except (
            TransparencyGossipBundleStructureError,
            TransparencyGossipBundleSignatureError,
        ) as error:
            raise TransparencyGossipBundleConflictError(
                _CONFLICT_MESSAGE
            ) from error

        expected_fields = {
            "log_id": checkpoint.log_id,
            "checkpoint_sha256": checkpoint.checkpoint_sha256,
            "checkpoint_signature_sha256": calculate_sha256_bytes(
                checkpoint_sig_bytes
            ),
            "artifact_type": artifact_type,
            "artifact_identifier": artifact_identifier,
            "artifact_sha256": artifact_sha256,
            "inclusion_proof_sha256": inclusion_digest,
            "consistency_proof_sha256": consistency_digest,
            "witness_trust_store_sha256": calculate_sha256_bytes(
                trust_bytes
            ),
            "witness_statement_sha256s": statement_digests,
            "required_witness_quorum": quorum.required_quorum,
        }

        if any(
            getattr(loaded.manifest, field) != expected
            for field, expected in expected_fields.items()
        ):
            raise TransparencyGossipBundleConflictError(
                _CONFLICT_MESSAGE
            )

        return TransparencyGossipBundleCreationResult(
            bundle_id=loaded.manifest.bundle_id,
            bundle_sha256=loaded.bundle_sha256,
            member_count=len(loaded.members),
            artifact_identifier=loaded.manifest.artifact_identifier,
            artifact_sha256=loaded.manifest.artifact_sha256,
            checkpoint_sha256=loaded.manifest.checkpoint_sha256,
            required_witness_quorum=(
                loaded.manifest.required_witness_quorum
            ),
            witness_count=len(
                loaded.manifest.witness_statement_sha256s
            ),
            bundle_reused=True,
        )

    signing_key = load_gossip_bundle_signing_private_key(environ=environ)
    bundle_id = calculate_gossip_bundle_id(
        log_id=checkpoint.log_id,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        artifact_type=artifact_type,
        artifact_identifier=artifact_identifier,
        artifact_sha256=artifact_sha256,
        inclusion_proof_sha256=inclusion_digest,
        witness_statement_sha256s=statement_digests,
        required_witness_quorum=quorum.required_quorum,
    )
    manifest = TransparencyGossipBundleManifestPayload(
        manifest_version=TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_VERSION,
        manifest_type=TRANSPARENCY_GOSSIP_BUNDLE_MANIFEST_TYPE,
        bundle_id=bundle_id,
        log_id=checkpoint.log_id,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        checkpoint_signature_sha256=calculate_sha256_bytes(checkpoint_sig_bytes),
        artifact_type=artifact_type,
        artifact_identifier=artifact_identifier,
        artifact_sha256=artifact_sha256,
        inclusion_proof_sha256=inclusion_digest,
        consistency_proof_sha256=consistency_digest,
        witness_trust_store_sha256=calculate_sha256_bytes(trust_bytes),
        witness_statement_sha256s=statement_digests,
        required_witness_quorum=quorum.required_quorum,
        created_at=normalize_aware_datetime(created_at),
        bundle_signing_key_id=signing_key.key_id,
    )
    signature = sign_gossip_bundle_manifest(manifest=manifest, signing_key=signing_key, signed_at=created_at)
    members: list[tuple[str, bytes]] = [
        (MANIFEST_MEMBER, _pretty_json(manifest)),
        (MANIFEST_SIGNATURE_MEMBER, _pretty_json(signature)),
        (CHECKPOINT_MEMBER, checkpoint_bytes),
        (CHECKPOINT_SIGNATURE_MEMBER, checkpoint_sig_bytes),
        (INCLUSION_PROOF_MEMBER, inclusion_bytes),
        (WITNESS_TRUST_STORE_MEMBER, trust_bytes),
        (ARTIFACT_BINDING_MEMBER, _pretty_json(binding)),
    ]
    if consistency_bytes is not None:
        members.append((CONSISTENCY_PROOF_MEMBER, consistency_bytes))
    members.extend(witness_members)
    _export_zip(path=output_path, members=tuple(members))
    return TransparencyGossipBundleCreationResult(
        bundle_id=bundle_id,
        bundle_sha256=_sha256_file(output_path),
        member_count=len(members),
        artifact_identifier=artifact_identifier,
        artifact_sha256=artifact_sha256,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        required_witness_quorum=quorum.required_quorum,
        witness_count=len(witness_members),
        bundle_reused=False,
    )


def sign_gossip_bundle_manifest(
    *,
    manifest: TransparencyGossipBundleManifestPayload,
    signing_key: GossipBundleSigningPrivateKey,
    signed_at: datetime,
) -> TransparencyGossipBundleManifestSignaturePayload:
    signature = Ed25519PrivateKey.from_private_bytes(signing_key.private_key_bytes).sign(
        TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_DOMAIN + b"\0" + canonicalize_gossip_bundle_manifest(manifest)
    )
    return TransparencyGossipBundleManifestSignaturePayload(
        signature_version=TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_VERSION,
        signature_type=TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_TYPE,
        algorithm=TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_ALGORITHM,
        bundle_signing_key_id=signing_key.key_id,
        bundle_id=manifest.bundle_id,
        manifest_sha256=gossip_bundle_manifest_digest(manifest),
        signature_b64=base64.b64encode(signature).decode("ascii"),
        signed_at=normalize_aware_datetime(signed_at),
    )


def load_transparency_gossip_bundle(*, path: Path) -> LoadedGossipBundle:
    members = _read_zip(path=path)
    manifest = TransparencyGossipBundleManifestPayload.model_validate_json(members[MANIFEST_MEMBER].decode("utf-8"))
    signature = TransparencyGossipBundleManifestSignaturePayload.model_validate_json(
        members[MANIFEST_SIGNATURE_MEMBER].decode("utf-8")
    )
    return LoadedGossipBundle(
        bundle_path=path,
        bundle_sha256=_sha256_file(path),
        members=members,
        manifest=manifest,
        manifest_signature=signature,
    )


def verify_gossip_bundle_manifest_signature(
    *, loaded: LoadedGossipBundle, trust_store: GossipBundleSigningTrustStore
) -> None:
    manifest = loaded.manifest
    signature = loaded.manifest_signature
    if signature.bundle_id != manifest.bundle_id or signature.manifest_sha256 != gossip_bundle_manifest_digest(manifest):
        raise TransparencyGossipBundleSignatureError(_MESSAGE)
    public_key = Ed25519PublicKey.from_public_bytes(trust_store.get_public_key(signature.bundle_signing_key_id))
    try:
        public_key.verify(
            _decode_b64(signature.signature_b64, expected_size=RAW_ED25519_SIGNATURE_BYTES),
            TRANSPARENCY_GOSSIP_BUNDLE_SIGNATURE_DOMAIN + b"\0" + canonicalize_gossip_bundle_manifest(manifest),
        )
    except InvalidSignature as error:
        raise TransparencyGossipBundleSignatureError(_MESSAGE) from error


def load_artifact_binding_from_bytes(data: bytes) -> TransparencyArtifactBindingPayload:
    try:
        return TransparencyArtifactBindingPayload.model_validate_json(data.decode("utf-8"))
    except (UnicodeDecodeError, ValidationError, ValueError) as error:
        raise TransparencyArtifactBindingError("The transparency artifact binding is invalid.") from error


def validate_artifact_binding(
    *,
    binding: TransparencyArtifactBindingPayload,
    manifest: TransparencyGossipBundleManifestPayload,
    inclusion_entry_hash: str,
    inclusion_sequence: int,
) -> None:
    if (
        binding.artifact_type != manifest.artifact_type
        or binding.artifact_identifier != manifest.artifact_identifier
        or binding.artifact_sha256 != manifest.artifact_sha256
        or binding.checkpoint_sha256 != manifest.checkpoint_sha256
        or binding.inclusion_proof_sha256 != manifest.inclusion_proof_sha256
        or binding.transparency_entry_hash != inclusion_entry_hash
        or binding.transparency_entry_sequence != inclusion_sequence
    ):
        raise TransparencyArtifactBindingError("The transparency artifact binding is invalid.")


def _read_zip(*, path: Path) -> dict[str, bytes]:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_GOSSIP_BUNDLE_BYTES:
            raise TransparencyGossipBundleStructureError(_MESSAGE)
        with ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_GOSSIP_BUNDLE_MEMBERS:
                raise TransparencyGossipBundleStructureError(_MESSAGE)
            names: set[str] = set()
            total = 0
            members: dict[str, bytes] = {}
            for info in infos:
                _validate_zip_info(info)
                if info.filename in names:
                    raise TransparencyGossipBundleStructureError(_MESSAGE)
                names.add(info.filename)
                total += info.file_size
                if total > MAX_GOSSIP_BUNDLE_TOTAL_BYTES:
                    raise TransparencyGossipBundleStructureError(_MESSAGE)
                members[info.filename] = archive.read(info)
    except (OSError, BadZipFile, LargeZipFile, RuntimeError) as error:
        raise TransparencyGossipBundleStructureError(_MESSAGE) from error
    required = {
        MANIFEST_MEMBER,
        MANIFEST_SIGNATURE_MEMBER,
        CHECKPOINT_MEMBER,
        CHECKPOINT_SIGNATURE_MEMBER,
        INCLUSION_PROOF_MEMBER,
        WITNESS_TRUST_STORE_MEMBER,
        ARTIFACT_BINDING_MEMBER,
    }
    if not required.issubset(members):
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    allowed = set(required) | {CONSISTENCY_PROOF_MEMBER}
    for name in members:
        if name.startswith("witnesses/") and name.endswith(".statement.json"):
            continue
        if name not in allowed:
            raise TransparencyGossipBundleStructureError(_MESSAGE)
    return members


def _validate_zip_info(info: ZipInfo) -> None:
    if not _safe_member_name(info.filename) or info.is_dir() or info.flag_bits & 0x1:
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    mode = info.external_attr >> 16
    if info.create_system == 3 and stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    if info.file_size > MAX_GOSSIP_BUNDLE_MEMBER_BYTES:
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    if (
        info.file_size >= COMPRESSION_RATIO_MINIMUM_SIZE
        and info.compress_size > 0
        and (info.file_size / info.compress_size) > MAX_ARCHIVE_COMPRESSION_RATIO
    ):
        raise TransparencyGossipBundleStructureError(_MESSAGE)


def _safe_member_name(name: str) -> bool:
    if not isinstance(name, str) or not name or name != name.strip() or "\0" in name or "\\" in name:
        return False
    if name.startswith("/") or ":" in name:
        return False
    parts = name.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _export_zip(*, path: Path, members: tuple[tuple[str, bytes], ...]) -> None:
    if path.is_symlink() or path.is_dir():
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    temp_path: Path | None = None
    replaced = False
    dir_fd: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as tmp:
            temp_path = Path(tmp.name)
        with ZipFile(temp_path, "w", compression=ZIP_DEFLATED, compresslevel=9, allowZip64=False) as archive:
            for name, data in members:
                info = ZipInfo(name, date_time=ZIP_MEMBER_TIMESTAMP)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = ZIP_MEMBER_MODE << 16
                archive.writestr(info, data)
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.chmod(temp_path, GOSSIP_BUNDLE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except (OSError, BadZipFile, LargeZipFile) as error:
        raise TransparencyGossipBundleStructureError(_MESSAGE) from error
    finally:
        if dir_fd is not None:
            try:
                os.close(dir_fd)
            except OSError:
                pass
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _witness_member_name(witness_id: str) -> str:
    if not is_valid_witness_id(witness_id):
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    return f"witnesses/{hashlib.sha256(witness_id.encode('utf-8')).hexdigest()}.statement.json"


def _sha256_file(path: Path) -> str:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyGossipBundleStructureError(_MESSAGE)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise TransparencyGossipBundleStructureError(_MESSAGE) from error


def _pretty_json(model: BaseModel) -> bytes:
    return (json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False).rstrip("\n") + "\n").encode("utf-8")


def _canonicalize_model(model: BaseModel) -> bytes:
    return _canonicalize_mapping(model.model_dump(mode="json"))


def _canonicalize_mapping(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_json_file(*, path: Path, max_bytes: int) -> object:
    if path.is_symlink() or path.is_dir():
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
        return _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE) from error


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyGossipBundleStructureError(_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _env_text(environ: dict[str, str] | os._Environ[str], name: str) -> str:
    value = environ.get(name)  # type: ignore[attr-defined]
    if not value:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    return value


def _env_b64(environ: dict[str, str] | os._Environ[str], name: str, expected_size: int) -> bytes:
    value = _env_text(environ, name)
    return _decode_b64(value, expected_size=expected_size)


def _decode_b64(value: object, *, expected_size: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE) from error
    if len(decoded) != expected_size:
        raise TransparencyGossipBundleConfigurationError(_CONFIG_MESSAGE)
    return decoded
