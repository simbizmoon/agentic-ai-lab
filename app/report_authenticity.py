"""HMAC authentication helpers for exported audit reports."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.audit_report import validate_audit_report_json
from app.authentication_keyring import MINIMUM_HMAC_KEY_BYTES, is_valid_key_id
from app.authentication_trust import (
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
    ensure_key_trusted_for_verification,
    parse_aware_datetime,
)
from app.exceptions import (
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationTrustStoreError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
)

HMAC_ALGORITHM = "hmac-sha256-v2"
HMAC_PROTOCOL_VERSION = 2
HMAC_CHUNK_SIZE = 64 * 1024
HMAC_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"audit-report:"
    b"hmac-sha256:"
    b"v2"
)
MAX_AUTHENTICATION_CLOCK_SKEW = timedelta(minutes=5)
_READ_ERROR_MESSAGE = "Failed to read the audit report authentication file."
_FORMAT_ERROR_MESSAGE = "The audit report authentication file has an invalid format."
_EXPORT_ERROR_MESSAGE = "Failed to export the audit report authentication file."

ReportAuthenticationKey = TrustedAuthenticationKey


@dataclass(frozen=True)
class ReportAuthentication:
    algorithm: str
    protocol_version: int
    key_id: str
    authenticated_at: datetime
    digest: str
    filename: str


@dataclass(frozen=True)
class ReportAuthenticityResult:
    algorithm: str
    key_id: str
    authenticated_at: datetime
    digest: str
    filename: str


def is_valid_hmac_digest(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def authentication_path_for(
    report_path: Path,
) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    return report_path.parent / f"{report_path.name}.hmac"



def calculate_report_hmac_bytes(
    *,
    filename: str,
    data: bytes,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    digest = _create_report_hmac(
        filename=filename,
        key=key,
        authenticated_at=authenticated_at,
    )
    digest.update(data)
    return digest.hexdigest()


def _create_report_hmac(
    *,
    filename: str,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
) -> hmac.HMAC:
    if not isinstance(filename, str):
        raise TypeError("filename must be a str")
    _validate_authentication_filename(filename)
    _validate_authentication_key(key)
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    authenticated_at_text = authenticated_at.isoformat()
    digest = hmac.new(key.secret, digestmod="sha256")
    digest.update(HMAC_DOMAIN_SEPARATOR)
    digest.update(b"\0")
    digest.update(key.key_id.encode("ascii"))
    digest.update(b"\0")
    digest.update(authenticated_at_text.encode("ascii"))
    digest.update(b"\0")
    digest.update(filename.encode("utf-8"))
    digest.update(b"\0")
    return digest


def calculate_report_hmac(
    *,
    report_path: Path,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
) -> str:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    try:
        if report_path.is_symlink() or not report_path.is_file():
            raise ReportAuthenticationReadError(_READ_ERROR_MESSAGE)
        digest = _create_report_hmac(
            filename=report_path.name,
            key=key,
            authenticated_at=authenticated_at,
        )
        with report_path.open("rb") as file:
            while chunk := file.read(HMAC_CHUNK_SIZE):
                digest.update(chunk)
    except ReportAuthenticationReadError:
        raise
    except OSError as error:
        raise ReportAuthenticationReadError(_READ_ERROR_MESSAGE) from error
    return digest.hexdigest()


def build_report_authentication(
    *,
    report_path: Path,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
) -> ReportAuthentication:
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    return ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id=key.key_id,
        authenticated_at=authenticated_at,
        digest=calculate_report_hmac(
            report_path=report_path,
            key=key,
            authenticated_at=authenticated_at,
        ),
        filename=report_path.name,
    )


def format_report_authentication(
    authentication: ReportAuthentication,
) -> str:
    if authentication.algorithm != HMAC_ALGORITHM:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if authentication.protocol_version != HMAC_PROTOCOL_VERSION:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_key_id(authentication.key_id):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    authenticated_at = _normalize_aware_datetime(authentication.authenticated_at)
    if not is_valid_hmac_digest(authentication.digest):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    _validate_authentication_filename(authentication.filename)
    return (
        f"{authentication.algorithm}  "
        f"{authentication.key_id}  "
        f"{authenticated_at.isoformat()}  "
        f"{authentication.digest}  "
        f"{authentication.filename}\n"
    )


def parse_report_authentication(
    text: str,
) -> ReportAuthentication:
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if text.endswith("\n\n"):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)

    body = text.removesuffix("\n")
    if "\n" in body or "\r" in body:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    fields = body.split("  ")
    if len(fields) != 5 or any(field == "" for field in fields):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)

    algorithm, key_id, authenticated_at_text, digest, filename = fields
    if algorithm != HMAC_ALGORITHM:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_hmac_digest(digest):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    _validate_authentication_filename(filename)
    try:
        authenticated_at = parse_aware_datetime(authenticated_at_text)
    except InvalidAuthenticationTrustStoreError as error:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE) from error
    return ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id=key_id,
        authenticated_at=authenticated_at,
        digest=digest,
        filename=filename,
    )


def export_authentication_file(
    *,
    authentication_path: Path,
    authentication: ReportAuthentication,
) -> None:
    if not isinstance(authentication_path, Path):
        raise TypeError("authentication_path must be a Path")
    if authentication_path.suffix != ".hmac":
        raise AuthenticationExportError(_EXPORT_ERROR_MESSAGE)
    if authentication_path.is_dir() or authentication_path.is_symlink():
        raise AuthenticationExportError(_EXPORT_ERROR_MESSAGE)

    authentication_text = format_report_authentication(authentication)
    temp_path: Path | None = None
    replaced = False

    try:
        authentication_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=authentication_path.parent,
            prefix=f".{authentication_path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(authentication_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, authentication_path)
        replaced = True
    except OSError as error:
        raise AuthenticationExportError(_EXPORT_ERROR_MESSAGE) from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def verify_report_authenticity(
    *,
    report_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    authentication_path: Path | None = None,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> ReportAuthenticityResult:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    if not isinstance(trust_store, AuthenticationTrustStore):
        raise TypeError("trust_store must be an AuthenticationTrustStore")
    verification_time = _normalize_aware_datetime(verification_time)
    if authentication_path is None:
        authentication_path = authentication_path_for(report_path)
    if not isinstance(authentication_path, Path):
        raise TypeError("authentication_path must be a Path")

    try:
        authentication_text = authentication_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportAuthenticationReadError(_READ_ERROR_MESSAGE) from error

    authentication = parse_report_authentication(authentication_text)
    if authentication.filename != report_path.name:
        raise AuthenticationFilenameMismatchError(
            "The authentication filename does not match the audit report."
        )
    key = trust_store.get_key(authentication.key_id)
    ensure_key_trusted_for_verification(
        key=key,
        authenticated_at=authentication.authenticated_at,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    actual_digest = calculate_report_hmac(
        report_path=report_path,
        key=key,
        authenticated_at=authentication.authenticated_at,
    )
    if not hmac.compare_digest(authentication.digest, actual_digest):
        raise ReportAuthenticityMismatchError(
            "The audit report authentication code does not match."
        )

    try:
        report_text = report_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportAuthenticationReadError(_READ_ERROR_MESSAGE) from error
    validate_audit_report_json(report_text)

    return ReportAuthenticityResult(
        algorithm=authentication.algorithm,
        key_id=authentication.key_id,
        authenticated_at=authentication.authenticated_at,
        digest=actual_digest,
        filename=authentication.filename,
    )


def _validate_authentication_key(key: TrustedAuthenticationKey) -> None:
    if not isinstance(key, TrustedAuthenticationKey):
        raise TypeError("key must be a TrustedAuthenticationKey")
    if not is_valid_key_id(key.key_id):
        raise InvalidAuthenticationKeyIdError(
            "The audit report authentication key ID is invalid."
        )
    if not isinstance(key.secret, bytes) or len(key.secret) < MINIMUM_HMAC_KEY_BYTES:
        raise InvalidAuthenticationKeyError(
            "The audit report authentication key is invalid."
        )


def _validate_authentication_filename(filename: str) -> None:
    if not filename:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if filename != filename.strip():
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if filename in {".", ".."}:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if "/" in filename or "\\" in filename:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if Path(filename).name != filename:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    return value.astimezone(UTC)
