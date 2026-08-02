"""Ed25519 signatures for exported audit report archives."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.archive_authenticity import (
    MAX_ARCHIVE_COMPRESSED_BYTES,
    REPORT_ARCHIVE_FORMAT_VERSION,
)
from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    ArchiveSignatureArchiveDigestMismatchError,
    ArchiveSignatureExportError,
    ArchiveSignatureFilenameMismatchError,
    ArchiveSignatureReadError,
    ArchiveSignatureValidationError,
    ArchiveSignatureVerificationError,
    ArchiveSigningKeyFingerprintMismatchError,
)
from app.report_integrity import (
    calculate_sha256_bytes,
    is_valid_sha256_digest,
)
from app.signature_trust import (
    ED25519_SIGNATURE_BYTES,
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    RevokedSignatureKeyPolicy,
    ensure_public_key_trusted_for_verification,
)

ARCHIVE_SIGNATURE_ALGORITHM = "ed25519-v1"
ARCHIVE_SIGNATURE_PROTOCOL_VERSION = 1
ARCHIVE_SIGNATURE_TYPE = "audit_report_archive_ed25519"
ARCHIVE_SIGNATURE_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"audit-report-archive:"
    b"ed25519-signature:"
    b"v1"
)
MAX_SIGNATURE_CLOCK_SKEW = timedelta(minutes=5)

_INVALID_SIGNATURE_MESSAGE = "The audit report archive signature failed validation."
_READ_SIGNATURE_MESSAGE = "Failed to read the audit report archive signature data."
_FILENAME_MESSAGE = "The archive signature filename does not match the archive."
_DIGEST_MESSAGE = "The archive signature digest does not match the archive."
_VERIFY_MESSAGE = "The audit report archive signature could not be verified."
_EXPORT_MESSAGE = "Failed to export the audit report archive signature file."


class ArchiveSignaturePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    signature_version: Literal[ARCHIVE_SIGNATURE_PROTOCOL_VERSION]
    signature_type: Literal[ARCHIVE_SIGNATURE_TYPE]
    algorithm: Literal[ARCHIVE_SIGNATURE_ALGORITHM]
    archive_format_version: int = Field(ge=1)
    key_id: str
    public_key_fingerprint: str
    signed_at: datetime
    archive_sha256: str
    signature_b64: str
    filename: str

    @field_validator("archive_format_version")
    @classmethod
    def _validate_archive_format_version(cls, value: int) -> int:
        if value != REPORT_ARCHIVE_FORMAT_VERSION:
            raise ValueError("unsupported archive format version")
        return value

    @field_validator("key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("public_key_fingerprint", "archive_sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid sha256 digest")
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature_b64(cls, value: str) -> str:
        signature = _decode_signature_b64(value)
        if len(signature) != ED25519_SIGNATURE_BYTES:
            raise ValueError("invalid signature length")
        return value

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        if not _is_valid_archive_filename(value):
            raise ValueError("invalid archive filename")
        return value


@dataclass(frozen=True)
class ArchiveSignatureVerificationResult:
    algorithm: str
    protocol_version: int
    archive_format_version: int
    key_id: str
    public_key_fingerprint: str
    signed_at: datetime
    archive_sha256: str
    filename: str


def archive_signature_path_for(archive_path: Path) -> Path:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not _is_valid_archive_filename(archive_path.name):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    return archive_path.with_name(f"{archive_path.name}.sig")


def build_archive_signature_message(
    *,
    filename: str,
    archive_bytes: bytes,
    archive_sha256: str,
    key_id: str,
    signed_at: datetime,
    archive_format_version: int,
) -> bytes:
    if not _is_valid_archive_filename(filename):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if not isinstance(archive_bytes, bytes):
        raise TypeError("archive_bytes must be bytes")
    if not is_valid_sha256_digest(archive_sha256):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if not is_valid_key_id(key_id):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    signed_at = _normalize_aware_datetime(signed_at)
    if not isinstance(archive_format_version, int) or isinstance(archive_format_version, bool):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if archive_format_version < 1:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)

    return b"\0".join(
        (
            ARCHIVE_SIGNATURE_DOMAIN_SEPARATOR,
            key_id.encode("ascii"),
            signed_at.isoformat().encode("ascii"),
            filename.encode("utf-8"),
            str(archive_format_version).encode("ascii"),
            archive_sha256.encode("ascii"),
            archive_bytes,
        )
    )


def sign_archive_bytes(
    *,
    filename: str,
    archive_bytes: bytes,
    signing_key: ArchiveSigningPrivateKey,
    signed_at: datetime,
    archive_format_version: int = REPORT_ARCHIVE_FORMAT_VERSION,
) -> ArchiveSignaturePayload:
    if not isinstance(archive_bytes, bytes):
        raise TypeError("archive_bytes must be bytes")
    if len(archive_bytes) > MAX_ARCHIVE_COMPRESSED_BYTES:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if not isinstance(signing_key, ArchiveSigningPrivateKey):
        raise TypeError("signing_key must be an ArchiveSigningPrivateKey")

    signed_at = _normalize_aware_datetime(signed_at)
    archive_sha256 = calculate_sha256_bytes(archive_bytes)
    message = build_archive_signature_message(
        filename=filename,
        archive_bytes=archive_bytes,
        archive_sha256=archive_sha256,
        key_id=signing_key.key_id,
        signed_at=signed_at,
        archive_format_version=archive_format_version,
    )
    signature = Ed25519PrivateKey.from_private_bytes(signing_key.private_key_bytes).sign(message)
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    return ArchiveSignaturePayload(
        signature_version=ARCHIVE_SIGNATURE_PROTOCOL_VERSION,
        signature_type=ARCHIVE_SIGNATURE_TYPE,
        algorithm=ARCHIVE_SIGNATURE_ALGORITHM,
        archive_format_version=archive_format_version,
        key_id=signing_key.key_id,
        public_key_fingerprint=signing_key.public_key_fingerprint,
        signed_at=signed_at,
        archive_sha256=archive_sha256,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        filename=filename,
    )


def sign_archive(
    *,
    archive_path: Path,
    signing_key: ArchiveSigningPrivateKey,
    signed_at: datetime,
    archive_format_version: int = REPORT_ARCHIVE_FORMAT_VERSION,
) -> ArchiveSignaturePayload:
    archive_bytes = _read_archive_bytes(archive_path)
    return sign_archive_bytes(
        filename=archive_path.name,
        archive_bytes=archive_bytes,
        signing_key=signing_key,
        signed_at=signed_at,
        archive_format_version=archive_format_version,
    )


def format_archive_signature_json(signature: ArchiveSignaturePayload) -> str:
    if not isinstance(signature, ArchiveSignaturePayload):
        raise TypeError("signature must be an ArchiveSignaturePayload")
    return json.dumps(
        signature.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def validate_archive_signature_json(json_text: str) -> ArchiveSignaturePayload:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        return ArchiveSignaturePayload.model_validate_json(json_text)
    except ValidationError as error:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE) from error


def export_archive_signature_file(
    *,
    path: Path,
    signature: ArchiveSignaturePayload,
) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.name.endswith(".bundle.zip.sig") is False:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if path.exists() and (path.is_dir() or path.is_symlink()):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)

    text = format_archive_signature_json(signature).rstrip("\n") + "\n"
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
        temp_path = None
    except OSError as error:
        raise ArchiveSignatureExportError(_EXPORT_MESSAGE) from error
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def verify_archive_signature(
    *,
    archive_path: Path,
    signature_trust_store: ArchiveSignatureTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedSignatureKeyPolicy = RevokedSignatureKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_SIGNATURE_CLOCK_SKEW,
    signature_path: Path | None = None,
) -> ArchiveSignatureVerificationResult:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not isinstance(signature_trust_store, ArchiveSignatureTrustStore):
        raise TypeError("signature_trust_store must be an ArchiveSignatureTrustStore")
    effective_signature_path = signature_path or archive_signature_path_for(archive_path)
    if not isinstance(effective_signature_path, Path):
        raise TypeError("signature_path must be a Path")

    archive_bytes = _read_archive_bytes(archive_path)
    try:
        signature_text = effective_signature_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArchiveSignatureReadError(_READ_SIGNATURE_MESSAGE) from error

    signature = validate_archive_signature_json(signature_text)
    if signature.filename != archive_path.name:
        raise ArchiveSignatureFilenameMismatchError(_FILENAME_MESSAGE)
    actual_sha256 = calculate_sha256_bytes(archive_bytes)
    if not hmac.compare_digest(signature.archive_sha256, actual_sha256):
        raise ArchiveSignatureArchiveDigestMismatchError(_DIGEST_MESSAGE)

    key = signature_trust_store.get_key(signature.key_id)
    if key.public_key_fingerprint != signature.public_key_fingerprint:
        raise ArchiveSigningKeyFingerprintMismatchError(
            "The archive signing key fingerprint does not match."
        )
    ensure_public_key_trusted_for_verification(
        key=key,
        signed_at=signature.signed_at,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )

    raw_signature = _decode_signature_b64(signature.signature_b64)
    message = build_archive_signature_message(
        filename=signature.filename,
        archive_bytes=archive_bytes,
        archive_sha256=signature.archive_sha256,
        key_id=signature.key_id,
        signed_at=signature.signed_at,
        archive_format_version=signature.archive_format_version,
    )
    try:
        Ed25519PublicKey.from_public_bytes(key.public_key_bytes).verify(raw_signature, message)
    except (InvalidSignature, ValueError) as error:
        raise ArchiveSignatureVerificationError(_VERIFY_MESSAGE) from error

    return ArchiveSignatureVerificationResult(
        algorithm=signature.algorithm,
        protocol_version=signature.signature_version,
        archive_format_version=signature.archive_format_version,
        key_id=signature.key_id,
        public_key_fingerprint=signature.public_key_fingerprint,
        signed_at=signature.signed_at,
        archive_sha256=signature.archive_sha256,
        filename=signature.filename,
    )


def _read_archive_bytes(archive_path: Path) -> bytes:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not _is_valid_archive_filename(archive_path.name):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ArchiveSignatureReadError(_READ_SIGNATURE_MESSAGE)
    try:
        if archive_path.stat().st_size > MAX_ARCHIVE_COMPRESSED_BYTES:
            raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
        return archive_path.read_bytes()
    except OSError as error:
        raise ArchiveSignatureReadError(_READ_SIGNATURE_MESSAGE) from error


def _decode_signature_b64(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid signature")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as error:
        raise ValueError("invalid signature") from error


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ArchiveSignatureValidationError(_INVALID_SIGNATURE_MESSAGE)
    return value.astimezone(UTC)


def _is_valid_archive_filename(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.endswith(".bundle.zip")
        and value.strip() == value
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and ":" not in value
        and "\0" not in value
        and Path(value).name == value
    )
