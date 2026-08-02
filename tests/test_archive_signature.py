from __future__ import annotations

import base64
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.archive_authenticity import REPORT_ARCHIVE_FORMAT_VERSION
from app.archive_signature import (
    ARCHIVE_SIGNATURE_ALGORITHM,
    ARCHIVE_SIGNATURE_DOMAIN_SEPARATOR,
    ARCHIVE_SIGNATURE_PROTOCOL_VERSION,
    ARCHIVE_SIGNATURE_TYPE,
    ArchiveSignaturePayload,
    ArchiveSignatureVerificationResult,
    archive_signature_path_for,
    build_archive_signature_message,
    export_archive_signature_file,
    format_archive_signature_json,
    sign_archive,
    sign_archive_bytes,
    validate_archive_signature_json,
    verify_archive_signature,
)
from app.exceptions import (
    ArchiveSignatureArchiveDigestMismatchError,
    ArchiveSignatureExportError,
    ArchiveSignatureFilenameMismatchError,
    ArchiveSignatureReadError,
    ArchiveSignatureValidationError,
    ArchiveSignatureVerificationError,
    ArchiveSigningKeyFingerprintMismatchError,
    UnknownArchiveSigningKeyError,
)
from app.report_integrity import calculate_sha256_bytes, is_valid_sha256_digest
from app.signature_trust import (
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    SignatureKeyStatus,
    TrustedArchiveSigningPublicKey,
    fingerprint_public_key,
)

SIGNED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFY_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
PRIVATE_TEXT = "PRIVATE-SIGNATURE-CONTENT"


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
        valid_from=datetime(2026, 8, 1, tzinfo=UTC),
    )


def trust_store(key: ArchiveSigningPrivateKey) -> ArchiveSignatureTrustStore:
    return ArchiveSignatureTrustStore(keys=(trusted_key(key),))


def archive_path(tmp_path: Path, data: bytes = b"zip bytes") -> Path:
    path = tmp_path / "audit-report.bundle.zip"
    path.write_bytes(data)
    return path


def test_archive_signature_path_for_uses_sig_suffix(tmp_path: Path) -> None:
    path = archive_signature_path_for(tmp_path / "report.bundle.zip")

    assert path.parent == tmp_path
    assert path.name == "report.bundle.zip.sig"


def test_archive_signature_path_for_rejects_non_archive_suffix(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSignatureValidationError):
        archive_signature_path_for(tmp_path / "report.zip")


def test_build_signature_message_contract() -> None:
    message = build_archive_signature_message(
        filename="report.bundle.zip",
        archive_bytes=b"abc",
        archive_sha256=calculate_sha256_bytes(b"abc"),
        key_id="sig-key",
        signed_at=SIGNED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )

    assert message.startswith(ARCHIVE_SIGNATURE_DOMAIN_SEPARATOR + b"\0sig-key\0")
    assert b"\0report.bundle.zip\0" in message
    assert message.endswith(b"\0abc")


def test_sign_archive_bytes_creates_payload() -> None:
    key = signing_key()
    payload = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT,
    )

    assert isinstance(payload, ArchiveSignaturePayload)
    assert payload.signature_version == ARCHIVE_SIGNATURE_PROTOCOL_VERSION
    assert payload.signature_type == ARCHIVE_SIGNATURE_TYPE
    assert payload.algorithm == ARCHIVE_SIGNATURE_ALGORITHM
    assert payload.key_id == key.key_id
    assert payload.public_key_fingerprint == key.public_key_fingerprint
    assert payload.archive_sha256 == calculate_sha256_bytes(b"archive")
    assert len(base64.b64decode(payload.signature_b64)) == 64


def test_sign_archive_path_matches_bytes(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")

    path_payload = sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT)
    bytes_payload = sign_archive_bytes(
        filename=path.name,
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT,
    )

    assert path_payload.archive_sha256 == bytes_payload.archive_sha256
    assert path_payload.signature_b64 == bytes_payload.signature_b64


def test_signature_changes_when_signed_fields_change() -> None:
    key = signing_key()
    first = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT,
    )
    changed_time = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT + timedelta(seconds=1),
    )
    changed_file = sign_archive_bytes(
        filename="other.bundle.zip",
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT,
    )
    changed_bytes = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"changed",
        signing_key=key,
        signed_at=SIGNED_AT,
    )

    assert first.signature_b64 != changed_time.signature_b64
    assert first.signature_b64 != changed_file.signature_b64
    assert first.signature_b64 != changed_bytes.signature_b64


def test_format_and_validate_signature_json_round_trip() -> None:
    payload = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes="서명".encode(),
        signing_key=signing_key(),
        signed_at=SIGNED_AT,
    )
    text = format_archive_signature_json(payload)

    assert json.loads(text)["algorithm"] == ARCHIVE_SIGNATURE_ALGORITHM
    assert "서명" not in text
    assert validate_archive_signature_json(text) == payload


def test_validate_signature_json_rejects_extra_fields_without_raw_json() -> None:
    payload = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=signing_key(),
        signed_at=SIGNED_AT,
    ).model_dump(mode="json")
    payload["private"] = PRIVATE_TEXT

    with pytest.raises(ArchiveSignatureValidationError) as exc_info:
        validate_archive_signature_json(json.dumps(payload))

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_export_signature_file_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=signing_key(),
        signed_at=SIGNED_AT,
    )
    path = tmp_path / "nested" / "report.bundle.zip.sig"
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

    monkeypatch.setattr("app.archive_signature.os.fsync", recording_fsync)
    monkeypatch.setattr("app.archive_signature.os.replace", recording_replace)

    export_archive_signature_file(path=path, signature=payload)

    assert path.is_file()
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert fsync_calls
    assert replace_calls[-1][1] == path
    assert not list(path.parent.glob("*.tmp"))


def test_export_signature_replace_failure_preserves_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = sign_archive_bytes(
        filename="report.bundle.zip",
        archive_bytes=b"archive",
        signing_key=signing_key(),
        signed_at=SIGNED_AT,
    )
    path = tmp_path / "report.bundle.zip.sig"
    path.write_text("existing", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_TEXT)

    monkeypatch.setattr("app.archive_signature.os.replace", fail_replace)

    with pytest.raises(ArchiveSignatureExportError) as exc_info:
        export_archive_signature_file(path=path, signature=payload)

    assert path.read_text(encoding="utf-8") == "existing"
    assert not list(tmp_path.glob("*.tmp"))
    assert PRIVATE_TEXT not in str(exc_info.value)


def test_verify_archive_signature_success_without_hmac_secret_or_private_key(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    payload = sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT)
    export_archive_signature_file(path=archive_signature_path_for(path), signature=payload)

    result = verify_archive_signature(
        archive_path=path,
        signature_trust_store=trust_store(key),
        verification_time=VERIFY_TIME,
    )

    assert isinstance(result, ArchiveSignatureVerificationResult)
    assert result.key_id == key.key_id
    assert result.archive_sha256 == calculate_sha256_bytes(b"archive")
    assert is_valid_sha256_digest(result.public_key_fingerprint)


def test_verify_archive_signature_detects_archive_tamper(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    export_archive_signature_file(
        path=archive_signature_path_for(path),
        signature=sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT),
    )
    path.write_bytes(b"changed")

    with pytest.raises(ArchiveSignatureArchiveDigestMismatchError):
        verify_archive_signature(
            archive_path=path,
            signature_trust_store=trust_store(key),
            verification_time=VERIFY_TIME,
        )


def test_verify_archive_signature_detects_signature_tamper(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    payload = sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT)
    data = payload.model_dump(mode="json")
    data["signature_b64"] = base64.b64encode(b"x" * 64).decode("ascii")
    archive_signature_path_for(path).write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ArchiveSignatureVerificationError):
        verify_archive_signature(
            archive_path=path,
            signature_trust_store=trust_store(key),
            verification_time=VERIFY_TIME,
        )


def test_verify_archive_signature_rejects_filename_mismatch(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    payload = sign_archive_bytes(
        filename="other.bundle.zip",
        archive_bytes=b"archive",
        signing_key=key,
        signed_at=SIGNED_AT,
    )
    archive_signature_path_for(path).write_text(format_archive_signature_json(payload), encoding="utf-8")

    with pytest.raises(ArchiveSignatureFilenameMismatchError):
        verify_archive_signature(
            archive_path=path,
            signature_trust_store=trust_store(key),
            verification_time=VERIFY_TIME,
        )


def test_verify_archive_signature_rejects_unknown_key_id(tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    export_archive_signature_file(
        path=archive_signature_path_for(path),
        signature=sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT),
    )

    with pytest.raises(UnknownArchiveSigningKeyError):
        verify_archive_signature(
            archive_path=path,
            signature_trust_store=ArchiveSignatureTrustStore(keys=()),
            verification_time=VERIFY_TIME,
        )


def test_verify_archive_signature_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    key = signing_key()
    other = signing_key(key.key_id)
    path = archive_path(tmp_path, b"archive")
    export_archive_signature_file(
        path=archive_signature_path_for(path),
        signature=sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT),
    )

    with pytest.raises(ArchiveSigningKeyFingerprintMismatchError):
        verify_archive_signature(
            archive_path=path,
            signature_trust_store=trust_store(other),
            verification_time=VERIFY_TIME,
        )


def test_verify_archive_signature_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSignatureReadError):
        verify_archive_signature(
            archive_path=tmp_path / "missing.bundle.zip",
            signature_trust_store=ArchiveSignatureTrustStore(keys=()),
            verification_time=VERIFY_TIME,
        )


def test_verify_uses_compare_digest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"archive")
    export_archive_signature_file(
        path=archive_signature_path_for(path),
        signature=sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT),
    )
    calls: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def recording_compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr("app.archive_signature.hmac.compare_digest", recording_compare)

    verify_archive_signature(
        archive_path=path,
        signature_trust_store=trust_store(key),
        verification_time=VERIFY_TIME,
    )

    assert calls


def test_verify_signature_does_not_open_zip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key = signing_key()
    path = archive_path(tmp_path, b"not actually a zip")
    export_archive_signature_file(
        path=archive_signature_path_for(path),
        signature=sign_archive(archive_path=path, signing_key=key, signed_at=SIGNED_AT),
    )

    def fail_zip(*args: object, **kwargs: object) -> None:
        raise AssertionError("zip parser should not be used")

    monkeypatch.setattr("zipfile.ZipFile", fail_zip)

    verify_archive_signature(
        archive_path=path,
        signature_trust_store=trust_store(key),
        verification_time=VERIFY_TIME,
    )
