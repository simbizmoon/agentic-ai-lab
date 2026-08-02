"""Checksum sidecar helpers for exported audit reports."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.audit_report import validate_audit_report_json
from app.exceptions import (
    ChecksumExportError,
    ChecksumFilenameMismatchError,
    InvalidChecksumFormatError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
)

SHA256_CHUNK_SIZE = 64 * 1024
CHECKSUM_ALGORITHM = "sha256"
_READ_ERROR_MESSAGE = "Failed to read the audit report integrity file."
_INVALID_FORMAT_MESSAGE = "The audit report checksum file has an invalid format."


@dataclass(frozen=True)
class ReportChecksum:
    algorithm: str
    digest: str
    filename: str


@dataclass(frozen=True)
class ReportIntegrityResult:
    algorithm: str
    digest: str
    filename: str


def checksum_path_for(
    report_path: Path,
) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    return report_path.parent / f"{report_path.name}.sha256"


def is_valid_sha256_digest(
    value: object,
) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)



def calculate_sha256_bytes(
    data: bytes,
) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return hashlib.sha256(data).hexdigest()


def calculate_sha256(
    path: Path,
) -> str:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")

    try:
        if path.is_symlink() or not path.is_file():
            raise ReportIntegrityReadError(_READ_ERROR_MESSAGE)
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(SHA256_CHUNK_SIZE):
                digest.update(chunk)
    except ReportIntegrityReadError:
        raise
    except OSError as error:
        raise ReportIntegrityReadError(_READ_ERROR_MESSAGE) from error
    return digest.hexdigest()


def build_report_checksum(
    report_path: Path,
) -> ReportChecksum:
    return ReportChecksum(
        algorithm=CHECKSUM_ALGORITHM,
        digest=calculate_sha256(report_path),
        filename=report_path.name,
    )


def format_report_checksum(
    checksum: ReportChecksum,
) -> str:
    if checksum.algorithm != CHECKSUM_ALGORITHM:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if not is_valid_sha256_digest(checksum.digest):
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    _validate_checksum_filename(checksum.filename)
    return f"{checksum.digest}  {checksum.filename}\n"


def parse_report_checksum(
    text: str,
) -> ReportChecksum:
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if text.endswith("\n\n"):
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)

    body = text.removesuffix("\n")
    if "\n" in body or "\r" in body:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if body.count("  ") != 1:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)

    digest, filename = body.split("  ")
    if not is_valid_sha256_digest(digest):
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    _validate_checksum_filename(filename)
    return ReportChecksum(
        algorithm=CHECKSUM_ALGORITHM,
        digest=digest,
        filename=filename,
    )


def export_checksum_file(
    *,
    checksum_path: Path,
    checksum: ReportChecksum,
) -> None:
    if not isinstance(checksum_path, Path):
        raise TypeError("checksum_path must be a Path")
    if checksum_path.suffix.lower() != ".sha256":
        raise ChecksumExportError("Failed to export the audit report checksum.")
    if checksum_path.is_dir() or checksum_path.is_symlink():
        raise ChecksumExportError("Failed to export the audit report checksum.")

    checksum_text = format_report_checksum(checksum)
    temp_path: Path | None = None
    replaced = False

    try:
        checksum_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=checksum_path.parent,
            prefix=f".{checksum_path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(checksum_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, checksum_path)
        replaced = True
    except OSError as error:
        raise ChecksumExportError("Failed to export the audit report checksum.") from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def verify_report_integrity(
    *,
    report_path: Path,
    checksum_path: Path | None = None,
) -> ReportIntegrityResult:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    if checksum_path is None:
        checksum_path = checksum_path_for(report_path)
    if not isinstance(checksum_path, Path):
        raise TypeError("checksum_path must be a Path")

    try:
        checksum_text = checksum_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportIntegrityReadError(_READ_ERROR_MESSAGE) from error

    checksum = parse_report_checksum(checksum_text)
    if checksum.filename != report_path.name:
        raise ChecksumFilenameMismatchError(
            "The checksum filename does not match the audit report."
        )

    actual_digest = calculate_sha256(report_path)
    if not hmac.compare_digest(checksum.digest, actual_digest):
        raise ReportIntegrityMismatchError("The audit report checksum does not match.")

    try:
        report_text = report_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportIntegrityReadError(_READ_ERROR_MESSAGE) from error
    validate_audit_report_json(report_text)

    return ReportIntegrityResult(
        algorithm=checksum.algorithm,
        digest=actual_digest,
        filename=checksum.filename,
    )


def _validate_checksum_filename(filename: str) -> None:
    if not filename:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if filename != filename.strip():
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if filename in {".", ".."}:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if "/" in filename or "\\" in filename:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
    if Path(filename).name != filename:
        raise InvalidChecksumFormatError(_INVALID_FORMAT_MESSAGE)
