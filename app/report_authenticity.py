"""HMAC authentication helpers for exported audit reports."""

from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.audit_report import validate_audit_report_json
from app.authentication_keyring import (
    MINIMUM_HMAC_KEY_BYTES,
    AuthenticationKey,
    AuthenticationKeyring,
    is_valid_key_id,
    load_authentication_keyring,
)
from app.exceptions import (
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
)

HMAC_ALGORITHM = "hmac-sha256"
HMAC_PROTOCOL_VERSION = 1
HMAC_CHUNK_SIZE = 64 * 1024
HMAC_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"audit-report:"
    b"hmac-sha256:"
    b"v1"
)
_READ_ERROR_MESSAGE = "Failed to read the audit report authentication file."
_FORMAT_ERROR_MESSAGE = "The audit report authentication file has an invalid format."
_EXPORT_ERROR_MESSAGE = "Failed to export the audit report authentication file."

ReportAuthenticationKey = AuthenticationKey


@dataclass(frozen=True)
class ReportAuthentication:
    algorithm: str
    protocol_version: int
    key_id: str
    digest: str
    filename: str


@dataclass(frozen=True)
class ReportAuthenticityResult:
    algorithm: str
    key_id: str
    digest: str
    filename: str


def is_valid_hmac_digest(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def load_authentication_key(
    *,
    environ: Mapping[str, str],
) -> AuthenticationKey:
    return load_authentication_keyring(environ=environ).get_active_key()


def authentication_path_for(
    report_path: Path,
) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    return report_path.parent / f"{report_path.name}.hmac"


def calculate_report_hmac(
    *,
    report_path: Path,
    key: AuthenticationKey,
) -> str:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    _validate_authentication_key(key)

    try:
        if report_path.is_symlink() or not report_path.is_file():
            raise ReportAuthenticationReadError(_READ_ERROR_MESSAGE)
        digest = hmac.new(key.secret, digestmod="sha256")
        digest.update(HMAC_DOMAIN_SEPARATOR)
        digest.update(b"\0")
        digest.update(report_path.name.encode("utf-8"))
        digest.update(b"\0")
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
    key: AuthenticationKey,
) -> ReportAuthentication:
    return ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id=key.key_id,
        digest=calculate_report_hmac(report_path=report_path, key=key),
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
    if not is_valid_hmac_digest(authentication.digest):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    _validate_authentication_filename(authentication.filename)
    return (
        f"{authentication.algorithm}  "
        f"{authentication.key_id}  "
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
    if len(fields) != 4 or any(field == "" for field in fields):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)

    algorithm, key_id, digest, filename = fields
    if algorithm != HMAC_ALGORITHM:
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    if not is_valid_hmac_digest(digest):
        raise InvalidAuthenticationFormatError(_FORMAT_ERROR_MESSAGE)
    _validate_authentication_filename(filename)
    return ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id=key_id,
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


def validate_authentication_keyring(
    keyring: AuthenticationKeyring,
) -> None:
    if not isinstance(keyring, AuthenticationKeyring):
        raise TypeError("keyring must be an AuthenticationKeyring")


def verify_report_authenticity(
    *,
    report_path: Path,
    keyring: AuthenticationKeyring,
    authentication_path: Path | None = None,
) -> ReportAuthenticityResult:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    validate_authentication_keyring(keyring)
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
    key = keyring.get_key(authentication.key_id)
    actual_digest = calculate_report_hmac(report_path=report_path, key=key)
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
        digest=actual_digest,
        filename=authentication.filename,
    )


def _validate_authentication_key(key: AuthenticationKey) -> None:
    if not isinstance(key, AuthenticationKey):
        raise TypeError("key must be an AuthenticationKey")
    if not is_valid_key_id(key.key_id):
        raise InvalidAuthenticationKeyIdError("The audit report authentication key ID is invalid.")
    if not isinstance(key.secret, bytes) or len(key.secret) < MINIMUM_HMAC_KEY_BYTES:
        raise InvalidAuthenticationKeyError("The audit report authentication key is invalid.")


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
