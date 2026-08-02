from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    SigningKeyManifestDigestMismatchError,
    SigningKeyManifestExportError,
    SigningKeyManifestRollbackError,
    SigningKeyManifestSignatureVerificationError,
    SigningKeyManifestValidationError,
)
from app.root_signature_trust import (
    RootSigningPrivateKey,
    TrustedRootSigningPublicKey,
)
from app.root_signature_trust import (
    fingerprint_public_key as root_fingerprint,
)
from app.signature_trust import (
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    SignatureKeyStatus,
    TrustedArchiveSigningPublicKey,
    fingerprint_public_key,
)
from app.signing_key_manifest import (
    KEY_MANIFEST_SIGNATURE_ALGORITHM,
    SIGNING_KEY_MANIFEST_TYPE,
    SIGNING_KEY_MANIFEST_VERSION,
    SigningKeyManifestPayload,
    VerifiedSigningKeyManifest,
    build_key_manifest_signature_message,
    build_signing_key_manifest,
    canonicalize_signing_key_manifest,
    export_signing_key_manifest,
    export_signing_key_manifest_signature,
    sign_signing_key_manifest,
    signing_key_manifest_signature_path_for,
    validate_signing_key_manifest_json,
    verify_signing_key_manifest,
)

ISSUED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VALID_FROM = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
VERIFY_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
PRIVATE_TEXT = "PRIVATE-MANIFEST-CONTENT"


def private_bytes() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_bytes(secret: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def root_pair() -> tuple[RootSigningPrivateKey, TrustedRootSigningPublicKey]:
    secret = private_bytes()
    public = public_bytes(secret)
    return (
        RootSigningPrivateKey("root-key", secret, public, root_fingerprint(public)),
        TrustedRootSigningPublicKey("root-key", public, root_fingerprint(public)),
    )


def signing_key(key_id: str = "sig-key") -> ArchiveSigningPrivateKey:
    secret = private_bytes()
    public = public_bytes(secret)
    return ArchiveSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=secret,
        public_key_bytes=public,
        public_key_fingerprint=fingerprint_public_key(public),
    )


def trusted_key(
    key: ArchiveSigningPrivateKey,
    *,
    status: SignatureKeyStatus = SignatureKeyStatus.ACTIVE,
) -> TrustedArchiveSigningPublicKey:
    return TrustedArchiveSigningPublicKey(
        key_id=key.key_id,
        public_key_bytes=key.public_key_bytes,
        public_key_fingerprint=key.public_key_fingerprint,
        status=status,
        valid_from=VALID_FROM,
    )


def manifest_for(
    root_public: TrustedRootSigningPublicKey,
    key: ArchiveSigningPrivateKey,
    *,
    generation: int = 1,
) -> SigningKeyManifestPayload:
    return build_signing_key_manifest(
        generation=generation,
        issued_at=ISSUED_AT,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
        root_public_key=root_public,
        keys=(trusted_key(key),),
    )


def write_manifest_bundle(
    tmp_path: Path,
    *,
    manifest: SigningKeyManifestPayload,
    root_private: RootSigningPrivateKey,
) -> Path:
    path = tmp_path / "signing-keys.json"
    signature = sign_signing_key_manifest(
        manifest=manifest,
        root_private_key=root_private,
        signed_at=ISSUED_AT,
        filename=path.name,
    )
    export_signing_key_manifest(path=path, manifest=manifest)
    export_signing_key_manifest_signature(
        path=signing_key_manifest_signature_path_for(path),
        signature=signature,
    )
    return path


def test_manifest_payload_and_signature_contract() -> None:
    root_private, root_public = root_pair()
    manifest = manifest_for(root_public, signing_key())
    signature = sign_signing_key_manifest(
        manifest=manifest,
        root_private_key=root_private,
        signed_at=ISSUED_AT,
        filename="signing-keys.json",
    )

    assert manifest.manifest_version == SIGNING_KEY_MANIFEST_VERSION
    assert manifest.manifest_type == SIGNING_KEY_MANIFEST_TYPE
    assert signature.algorithm == KEY_MANIFEST_SIGNATURE_ALGORITHM
    assert signature.root_key_id == root_public.key_id
    assert signature.filename == "signing-keys.json"


def test_validate_manifest_rejects_duplicate_json_keys_without_raw_content() -> None:
    text = '{"manifest_version":1,"manifest_version":1,"private":"PRIVATE-MANIFEST-CONTENT"}'

    with pytest.raises(SigningKeyManifestValidationError) as exc_info:
        validate_signing_key_manifest_json(text)

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_canonical_manifest_signature_survives_pretty_formatting(tmp_path: Path) -> None:
    root_private, root_public = root_pair()
    key = signing_key()
    manifest = manifest_for(root_public, key)
    path = write_manifest_bundle(tmp_path, manifest=manifest, root_private=root_private)
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")

    verified = verify_signing_key_manifest(
        manifest_path=path,
        root_public_key=root_public,
        verification_time=VERIFY_TIME,
    )

    assert isinstance(verified, VerifiedSigningKeyManifest)
    assert verified.result.active_key_id == key.key_id
    assert verified.trust_store.get_key(key.key_id).public_key_bytes == key.public_key_bytes


def test_meaningful_manifest_change_fails_signature(tmp_path: Path) -> None:
    root_private, root_public = root_pair()
    manifest = manifest_for(root_public, signing_key())
    path = write_manifest_bundle(tmp_path, manifest=manifest, root_private=root_private)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["generation"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SigningKeyManifestDigestMismatchError):
        verify_signing_key_manifest(
            manifest_path=path,
            root_public_key=root_public,
            verification_time=VERIFY_TIME,
        )


def test_manifest_signature_failure_prevents_trust_store_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_private, root_public = root_pair()
    manifest = manifest_for(root_public, signing_key())
    path = write_manifest_bundle(tmp_path, manifest=manifest, root_private=root_private)
    signature_path = signing_key_manifest_signature_path_for(path)
    signature_payload = json.loads(signature_path.read_text(encoding="utf-8"))
    signature_payload["signature_b64"] = base64.b64encode(b"x" * 64).decode("ascii")
    signature_path.write_text(json.dumps(signature_payload), encoding="utf-8")

    def fail_store(*args: object, **kwargs: object) -> ArchiveSignatureTrustStore:
        raise AssertionError("trust store must not be created")

    monkeypatch.setattr("app.signing_key_manifest.ArchiveSignatureTrustStore", fail_store)

    with pytest.raises(SigningKeyManifestSignatureVerificationError):
        verify_signing_key_manifest(
            manifest_path=path,
            root_public_key=root_public,
            verification_time=VERIFY_TIME,
        )


def test_minimum_generation_blocks_rollback(tmp_path: Path) -> None:
    root_private, root_public = root_pair()
    path = write_manifest_bundle(
        tmp_path,
        manifest=manifest_for(root_public, signing_key(), generation=2),
        root_private=root_private,
    )

    with pytest.raises(SigningKeyManifestRollbackError):
        verify_signing_key_manifest(
            manifest_path=path,
            root_public_key=root_public,
            verification_time=VERIFY_TIME,
            minimum_generation=3,
        )


def test_build_signature_message_contains_expected_domain_inputs() -> None:
    message = build_key_manifest_signature_message(
        canonical_manifest_bytes=b"canonical",
        manifest_sha256="0" * 64,
        root_key_id="root-key",
        manifest_version=1,
        generation=7,
    )

    assert b"archive-signing-key-manifest" in message
    assert b"root-key" in message
    assert message.endswith(b"canonical")


def test_export_manifest_files_are_atomic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_private, root_public = root_pair()
    manifest = manifest_for(root_public, signing_key())
    signature = sign_signing_key_manifest(
        manifest=manifest,
        root_private_key=root_private,
        signed_at=ISSUED_AT,
        filename="signing-keys.json",
    )
    path = tmp_path / "nested" / "signing-keys.json"
    fsync_calls: list[int] = []
    replace_calls: list[tuple[Path, Path]] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def recording_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        original_fsync(fd)

    def recording_replace(source: Path, destination: Path) -> None:
        replace_calls.append((source, destination))
        original_replace(source, destination)

    monkeypatch.setattr("app.signing_key_manifest.os.fsync", recording_fsync)
    monkeypatch.setattr("app.signing_key_manifest.os.replace", recording_replace)

    export_signing_key_manifest(path=path, manifest=manifest)
    export_signing_key_manifest_signature(
        path=signing_key_manifest_signature_path_for(path),
        signature=signature,
    )

    assert path.is_file()
    assert signing_key_manifest_signature_path_for(path).is_file()
    assert fsync_calls
    assert replace_calls
    assert not list(path.parent.glob("*.tmp"))


def test_export_failure_preserves_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _root_private, root_public = root_pair()
    path = tmp_path / "signing-keys.json"
    path.write_text("existing", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_TEXT)

    monkeypatch.setattr("app.signing_key_manifest.os.replace", fail_replace)

    with pytest.raises(SigningKeyManifestExportError) as exc_info:
        export_signing_key_manifest(
            path=path,
            manifest=manifest_for(root_public, signing_key()),
        )

    assert path.read_text(encoding="utf-8") == "existing"
    assert PRIVATE_TEXT not in str(exc_info.value)


def test_canonical_bytes_have_no_trailing_newline() -> None:
    _, root_public = root_pair()
    canonical = canonicalize_signing_key_manifest(manifest_for(root_public, signing_key()))

    assert not canonical.endswith(b"\n")
