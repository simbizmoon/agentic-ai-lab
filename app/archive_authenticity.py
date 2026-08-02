"""HMAC authentication helpers for exported audit report ZIP archives."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.authentication_keyring import is_valid_key_id
from app.authentication_trust import (
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
    ensure_key_trusted_for_verification,
)
from app.exceptions import (
    ArchiveAuthenticationExportError,
    ArchiveAuthenticationFilenameMismatchError,
    ArchiveAuthenticationFormatVersionMismatchError,
    ArchiveAuthenticationReadError,
    ArchiveAuthenticityMismatchError,
    InvalidArchiveAuthenticationFormatError,
)
from app.report_authenticity import MAX_AUTHENTICATION_CLOCK_SKEW
from app.report_integrity import is_valid_sha256_digest

REPORT_ARCHIVE_FORMAT_VERSION = 1
MAX_ARCHIVE_COMPRESSED_BYTES = 20 * 1024 * 1024

ARCHIVE_HMAC_ALGORITHM = "archive-hmac-sha256-v1"
ARCHIVE_HMAC_PROTOCOL_VERSION = 1
ARCHIVE_HMAC_CHUNK_SIZE = 64 * 1024
ARCHIVE_HMAC_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"audit-report-archive:"
    b"hmac-sha256:"
    b"v1"
)

_READ_ERROR_MESSAGE = "Failed to read the audit report archive authentication data."
_FORMAT_ERROR_MESSAGE = "The audit report archive authentication file has an invalid format."
_EXPORT_ERROR_MESSAGE = "Failed to export the audit report archive authentication file."
_FILENAME_MISMATCH_MESSAGE = "The archive authentication filename does not match the audit report archive."
_FORMAT_VERSION_MISMATCH_MESSAGE = "The archive authentication format version does not match."
_MISMATCH_MESSAGE = "The audit report archive authentication code does not match."


@dataclass(frozen=True)
class ArchiveAuthentication:
    algorithm: str
    protocol_version: int
    archive_format_version: int
    key_id: str
    authenticated_at: datetime
    digest: str
    filename: str


@dataclass(frozen=True)
class ArchiveAuthenticityResult:
    algorithm: str
    protocol_version: int
    archive_format_version: int
    key_id: str
    authenticated_at: datetime
    digest: str
    filename: str


def archive_authentication_path_for(
    archive_path: Path,
) -> Path:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not _validate_archive_filename(archive_path.name):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    return archive_path.parent / f"{archive_path.name}.hmac"


def calculate_archive_hmac_bytes(
    *,
    filename: str,
    data: bytes,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
    archive_format_version: int,
) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    digest = _create_archive_hmac(
        filename=filename,
        key=key,
        authenticated_at=authenticated_at,
        archive_format_version=archive_format_version,
    )
    digest.update(data)
    return digest.hexdigest()


def calculate_archive_hmac(
    *,
    archive_path: Path,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
    archive_format_version: int,
) -> str:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    try:
        if archive_path.is_symlink() or not archive_path.is_file():
            raise ArchiveAuthenticationReadError(_READ_ERROR_MESSAGE)
        if archive_path.stat().st_size > MAX_ARCHIVE_COMPRESSED_BYTES:
            raise ArchiveAuthenticationReadError(_READ_ERROR_MESSAGE)
        digest = _create_archive_hmac(
            filename=archive_path.name,
            key=key,
            authenticated_at=authenticated_at,
            archive_format_version=archive_format_version,
        )
        with archive_path.open("rb") as file:
            while chunk := file.read(ARCHIVE_HMAC_CHUNK_SIZE):
                digest.update(chunk)
    except ArchiveAuthenticationReadError:
        raise
    except OSError as error:
        raise ArchiveAuthenticationReadError(_READ_ERROR_MESSAGE) from error
    return digest.hexdigest()


def build_archive_authentication(
    *,
    archive_path: Path,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
    archive_format_version: int,
) -> ArchiveAuthentication:
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    return ArchiveAuthentication(
        algorithm=ARCHIVE_HMAC_ALGORITHM,
        protocol_version=ARCHIVE_HMAC_PROTOCOL_VERSION,
        archive_format_version=archive_format_version,
        key_id=key.key_id,
        authenticated_at=authenticated_at,
        digest=calculate_archive_hmac(
            archive_path=archive_path,
            key=key,
            authenticated_at=authenticated_at,
            archive_format_version=archive_format_version,
        ),
        filename=archive_path.name,
    )


def format_archive_authentication(
    authentication: ArchiveAuthentication,
) -> str:
    if not isinstance(authentication, ArchiveAuthentication):
        raise TypeError("authentication must be an ArchiveAuthentication")
    if authentication.algorithm != ARCHIVE_HMAC_ALGORITHM:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if authentication.protocol_version != ARCHIVE_HMAC_PROTOCOL_VERSION:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    _validate_archive_format_version(authentication.archive_format_version)
    if not is_valid_key_id(authentication.key_id):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    authenticated_at = _normalize_aware_datetime(authentication.authenticated_at)
    if not is_valid_sha256_digest(authentication.digest):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not _validate_archive_filename(authentication.filename):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    return (
        f"{authentication.algorithm}  "
        f"{authentication.archive_format_version}  "
        f"{authentication.key_id}  "
        f"{authenticated_at.isoformat()}  "
        f"{authentication.digest}  "
        f"{authentication.filename}\n"
    )


def parse_archive_authentication(
    text: str,
) -> ArchiveAuthentication:
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if text.endswith("\n\n"):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    body = text.removesuffix("\n")
    if "\n" in body or "\r" in body:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    fields = body.split("  ")
    if len(fields) != 6 or any(field == "" for field in fields):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)

    algorithm, archive_format_version_text, key_id, authenticated_at_text, digest, filename = fields
    if algorithm != ARCHIVE_HMAC_ALGORITHM:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    try:
        archive_format_version = int(archive_format_version_text)
    except ValueError as error:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE) from error
    if archive_format_version != REPORT_ARCHIVE_FORMAT_VERSION:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_key_id(key_id):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    try:
        authenticated_at = _normalize_aware_datetime(datetime.fromisoformat(authenticated_at_text))
    except ValueError as error:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE) from error
    if not is_valid_sha256_digest(digest):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not _validate_archive_filename(filename):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    return ArchiveAuthentication(
        algorithm=ARCHIVE_HMAC_ALGORITHM,
        protocol_version=ARCHIVE_HMAC_PROTOCOL_VERSION,
        archive_format_version=archive_format_version,
        key_id=key_id,
        authenticated_at=authenticated_at,
        digest=digest,
        filename=filename,
    )


def export_archive_authentication_file(
    *,
    path: Path,
    authentication: ArchiveAuthentication,
) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not path.name.endswith(".bundle.zip.hmac"):
        raise ArchiveAuthenticationExportError(_EXPORT_ERROR_MESSAGE)
    if path.is_dir() or path.is_symlink():
        raise ArchiveAuthenticationExportError(_EXPORT_ERROR_MESSAGE)

    authentication_text = format_archive_authentication(authentication)
    temp_path: Path | None = None
    replaced = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(authentication_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)
        replaced = True
    except OSError as error:
        raise ArchiveAuthenticationExportError(_EXPORT_ERROR_MESSAGE) from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def verify_archive_authenticity(
    *,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    expected_archive_format_version: int,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
    authentication_path: Path | None = None,
) -> ArchiveAuthenticityResult:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not isinstance(trust_store, AuthenticationTrustStore):
        raise TypeError("trust_store must be an AuthenticationTrustStore")
    verification_time = _normalize_aware_datetime(verification_time)
    _validate_archive_format_version(expected_archive_format_version)
    if authentication_path is None:
        authentication_path = archive_authentication_path_for(archive_path)
    if not isinstance(authentication_path, Path):
        raise TypeError("authentication_path must be a Path")

    try:
        authentication_text = authentication_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArchiveAuthenticationReadError(_READ_ERROR_MESSAGE) from error

    authentication = parse_archive_authentication(authentication_text)
    if authentication.filename != archive_path.name:
        raise ArchiveAuthenticationFilenameMismatchError(_FILENAME_MISMATCH_MESSAGE)
    if authentication.archive_format_version != expected_archive_format_version:
        raise ArchiveAuthenticationFormatVersionMismatchError(_FORMAT_VERSION_MISMATCH_MESSAGE)

    key = trust_store.get_key(authentication.key_id)
    ensure_key_trusted_for_verification(
        key=key,
        authenticated_at=authentication.authenticated_at,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    actual_digest = calculate_archive_hmac(
        archive_path=archive_path,
        key=key,
        authenticated_at=authentication.authenticated_at,
        archive_format_version=authentication.archive_format_version,
    )
    if not hmac.compare_digest(authentication.digest, actual_digest):
        raise ArchiveAuthenticityMismatchError(_MISMATCH_MESSAGE)

    return ArchiveAuthenticityResult(
        algorithm=authentication.algorithm,
        protocol_version=authentication.protocol_version,
        archive_format_version=authentication.archive_format_version,
        key_id=authentication.key_id,
        authenticated_at=authentication.authenticated_at,
        digest=actual_digest,
        filename=authentication.filename,
    )


def _create_archive_hmac(
    *,
    filename: str,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
    archive_format_version: int,
) -> hmac.HMAC:
    if not _validate_archive_filename(filename):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not isinstance(key, TrustedAuthenticationKey):
        raise TypeError("key must be a TrustedAuthenticationKey")
    if not is_valid_key_id(key.key_id):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    _validate_archive_format_version(archive_format_version)

    digest = hmac.new(key.secret, digestmod="sha256")
    digest.update(ARCHIVE_HMAC_DOMAIN_SEPARATOR)
    digest.update(b"\0")
    digest.update(key.key_id.encode("ascii"))
    digest.update(b"\0")
    digest.update(authenticated_at.isoformat().encode("ascii"))
    digest.update(b"\0")
    digest.update(filename.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(archive_format_version).encode("ascii"))
    digest.update(b"\0")
    return digest


def _validate_archive_filename(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip():
        return False
    if any(character in value for character in ("/", "\\", ":", "\0")):
        return False
    if not value.endswith(".bundle.zip"):
        return False
    return Path(value).name == value


def _validate_archive_format_version(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidArchiveAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    return value.astimezone(UTC)
