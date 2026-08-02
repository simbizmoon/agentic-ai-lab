"""Bundle manifest helpers for exported audit report artifacts."""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.audit_report import validate_audit_report_json
from app.authentication_keyring import is_valid_key_id
from app.authentication_trust import AuthenticationTrustStore, RevokedKeyPolicy
from app.exceptions import (
    BundleReportFilenameMismatchError,
    IncompleteReportBundleError,
    ReportBundleDigestMismatchError,
    ReportBundleExportError,
    ReportBundleManifestValidationError,
    ReportBundleMetadataMismatchError,
    ReportBundleReadError,
    ReportIntegrityMismatchError,
)
from app.report_authenticity import (
    HMAC_ALGORITHM,
    HMAC_PROTOCOL_VERSION,
    MAX_AUTHENTICATION_CLOCK_SKEW,
    authentication_path_for,
    parse_report_authentication,
    verify_report_authenticity,
)
from app.report_integrity import (
    calculate_sha256,
    checksum_path_for,
    is_valid_sha256_digest,
    parse_report_checksum,
    verify_report_integrity,
)

REPORT_BUNDLE_MANIFEST_VERSION = 1
REPORT_BUNDLE_TYPE = "structured_analysis_audit_report_bundle"
_VALIDATION_ERROR_MESSAGE = "The audit report bundle manifest failed validation."
_EXPORT_ERROR_MESSAGE = "Failed to export the audit report bundle manifest."
_READ_ERROR_MESSAGE = "Failed to read the audit report bundle manifest."
_INCOMPLETE_ERROR_MESSAGE = "The audit report bundle is incomplete."
_DIGEST_MISMATCH_MESSAGE = "The audit report bundle digest does not match."
_METADATA_MISMATCH_MESSAGE = "The audit report bundle metadata is inconsistent."
_FILENAME_MISMATCH_MESSAGE = "The bundle manifest references a different report filename."


class BundlePayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def is_valid_bundle_filename(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip():
        return False
    if value in {".", ".."}:
        return False
    if "/" in value or "\\" in value:
        return False
    return Path(value).name == value


class BundleReportEntry(BundlePayloadModel):
    filename: str
    schema_version: int = Field(ge=1)
    sha256: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not is_valid_bundle_filename(value) or Path(value).suffix.lower() != ".json":
            raise ValueError("filename must be a JSON bundle filename")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        return value


class BundleChecksumEntry(BundlePayloadModel):
    filename: str
    sha256: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not is_valid_bundle_filename(value) or not value.lower().endswith(".sha256"):
            raise ValueError("filename must be a checksum sidecar filename")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        return value


class BundleAuthenticationEntry(BundlePayloadModel):
    filename: str
    sha256: str
    algorithm: str
    protocol_version: int = Field(ge=1)
    key_id: str
    authenticated_at: datetime

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not is_valid_bundle_filename(value) or not value.lower().endswith(".hmac"):
            raise ValueError("filename must be an authentication sidecar filename")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        return value

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        if value != HMAC_ALGORITHM:
            raise ValueError("algorithm must match the current HMAC algorithm")
        return value

    @field_validator("protocol_version")
    @classmethod
    def validate_protocol_version(cls, value: int) -> int:
        if value != HMAC_PROTOCOL_VERSION:
            raise ValueError("protocol_version must match the current HMAC protocol")
        return value

    @field_validator("key_id")
    @classmethod
    def validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("key_id must be valid")
        return value

    @field_validator("authenticated_at")
    @classmethod
    def normalize_authenticated_at(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


class AuditReportBundleManifest(BundlePayloadModel):
    manifest_version: Literal[1]
    bundle_type: Literal["structured_analysis_audit_report_bundle"]
    report: BundleReportEntry
    checksum: BundleChecksumEntry
    authentication: BundleAuthenticationEntry

    @model_validator(mode="after")
    def validate_sidecar_filenames(self) -> Self:
        if self.checksum.filename != f"{self.report.filename}.sha256":
            raise ValueError("checksum filename must match report filename")
        if self.authentication.filename != f"{self.report.filename}.hmac":
            raise ValueError("authentication filename must match report filename")
        return self


@dataclass(frozen=True)
class ReportBundleVerificationResult:
    manifest_version: int
    report_schema_version: int
    authentication_protocol_version: int
    algorithm: str
    key_id: str
    authenticated_at: datetime
    report_filename: str


def manifest_path_for(report_path: Path) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    return report_path.parent / f"{report_path.name}.manifest"


def build_report_bundle_manifest(*, report_path: Path) -> AuditReportBundleManifest:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    checksum_path = checksum_path_for(report_path)
    authentication_path = authentication_path_for(report_path)
    _ensure_bundle_file_exists(report_path)
    _ensure_bundle_file_exists(checksum_path)
    _ensure_bundle_file_exists(authentication_path)

    report_payload = _read_and_validate_report_payload(report_path)
    checksum_text = _read_text(checksum_path)
    checksum = parse_report_checksum(checksum_text)
    if checksum.filename != report_path.name:
        raise BundleReportFilenameMismatchError(_FILENAME_MISMATCH_MESSAGE)
    actual_report_digest = calculate_sha256(report_path)
    if not hmac.compare_digest(checksum.digest, actual_report_digest):
        raise ReportIntegrityMismatchError("The audit report checksum does not match.")

    authentication_text = _read_text(authentication_path)
    authentication = parse_report_authentication(authentication_text)
    if authentication.filename != report_path.name:
        raise BundleReportFilenameMismatchError(_FILENAME_MISMATCH_MESSAGE)

    try:
        return AuditReportBundleManifest(
            manifest_version=REPORT_BUNDLE_MANIFEST_VERSION,
            bundle_type=REPORT_BUNDLE_TYPE,
            report=BundleReportEntry(
                filename=report_path.name,
                schema_version=report_payload.schema_version,
                sha256=actual_report_digest,
            ),
            checksum=BundleChecksumEntry(
                filename=checksum_path.name,
                sha256=calculate_sha256(checksum_path),
            ),
            authentication=BundleAuthenticationEntry(
                filename=authentication_path.name,
                sha256=calculate_sha256(authentication_path),
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                key_id=authentication.key_id,
                authenticated_at=authentication.authenticated_at,
            ),
        )
    except ValidationError as error:
        raise ReportBundleManifestValidationError(_VALIDATION_ERROR_MESSAGE) from error


def format_report_bundle_manifest(manifest: AuditReportBundleManifest) -> str:
    if not isinstance(manifest, AuditReportBundleManifest):
        raise TypeError("manifest must be an AuditReportBundleManifest")
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def validate_report_bundle_manifest_json(json_text: str) -> AuditReportBundleManifest:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        return AuditReportBundleManifest.model_validate_json(json_text)
    except ValidationError as error:
        raise ReportBundleManifestValidationError(_VALIDATION_ERROR_MESSAGE) from error


def export_report_bundle_manifest(*, path: Path, manifest: AuditReportBundleManifest) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.suffix != ".manifest":
        raise ReportBundleExportError(_EXPORT_ERROR_MESSAGE)
    if path.is_dir() or path.is_symlink():
        raise ReportBundleExportError(_EXPORT_ERROR_MESSAGE)

    manifest_text = format_report_bundle_manifest(manifest).rstrip("\n") + "\n"
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
            temp_file.write(manifest_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)
        replaced = True
    except OSError as error:
        raise ReportBundleExportError(_EXPORT_ERROR_MESSAGE) from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def verify_report_bundle(
    *,
    report_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
    manifest_path: Path | None = None,
) -> ReportBundleVerificationResult:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    if not isinstance(trust_store, AuthenticationTrustStore):
        raise TypeError("trust_store must be an AuthenticationTrustStore")
    verification_time = _normalize_aware_datetime(verification_time)
    if manifest_path is None:
        manifest_path = manifest_path_for(report_path)
    if not isinstance(manifest_path, Path):
        raise TypeError("manifest_path must be a Path")

    checksum_path = checksum_path_for(report_path)
    authentication_path = authentication_path_for(report_path)
    for path in (report_path, checksum_path, authentication_path, manifest_path):
        _ensure_bundle_file_exists(path)

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportBundleReadError(_READ_ERROR_MESSAGE) from error
    manifest = validate_report_bundle_manifest_json(manifest_text)

    if manifest.report.filename != report_path.name:
        raise BundleReportFilenameMismatchError(_FILENAME_MISMATCH_MESSAGE)

    _compare_manifest_digest(manifest.report.sha256, calculate_sha256(report_path))
    _compare_manifest_digest(manifest.checksum.sha256, calculate_sha256(checksum_path))
    _compare_manifest_digest(manifest.authentication.sha256, calculate_sha256(authentication_path))

    integrity_result = verify_report_integrity(report_path=report_path, checksum_path=checksum_path)
    authenticity_result = verify_report_authenticity(
        report_path=report_path,
        trust_store=trust_store,
        verification_time=verification_time,
        authentication_path=authentication_path,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    report_payload = _read_and_validate_report_payload(report_path)

    if integrity_result.filename != manifest.report.filename:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if report_payload.schema_version != manifest.report.schema_version:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authenticity_result.algorithm != manifest.authentication.algorithm:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if HMAC_PROTOCOL_VERSION != manifest.authentication.protocol_version:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authenticity_result.key_id != manifest.authentication.key_id:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if _normalize_aware_datetime(authenticity_result.authenticated_at) != manifest.authentication.authenticated_at:
        raise ReportBundleMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)

    return ReportBundleVerificationResult(
        manifest_version=manifest.manifest_version,
        report_schema_version=manifest.report.schema_version,
        authentication_protocol_version=manifest.authentication.protocol_version,
        algorithm=manifest.authentication.algorithm,
        key_id=manifest.authentication.key_id,
        authenticated_at=manifest.authentication.authenticated_at,
        report_filename=manifest.report.filename,
    )


def _ensure_bundle_file_exists(path: Path) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or not path.is_file():
        raise IncompleteReportBundleError(_INCOMPLETE_ERROR_MESSAGE)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportBundleReadError(_READ_ERROR_MESSAGE) from error


def _read_and_validate_report_payload(report_path: Path):
    try:
        report_text = report_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReportBundleReadError(_READ_ERROR_MESSAGE) from error
    return validate_audit_report_json(report_text)


def _compare_manifest_digest(expected: str, actual: str) -> None:
    if not hmac.compare_digest(expected, actual):
        raise ReportBundleDigestMismatchError(_DIGEST_MISMATCH_MESSAGE)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime must be timezone-aware")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)
