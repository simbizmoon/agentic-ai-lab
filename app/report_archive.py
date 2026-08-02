"""ZIP archive helpers for verified audit report bundles."""

from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, BadZipFile, LargeZipFile, ZipFile, ZipInfo

from app.archive_authenticity import (
    MAX_ARCHIVE_COMPRESSED_BYTES,
    REPORT_ARCHIVE_FORMAT_VERSION,
    ArchiveAuthentication,
    archive_authentication_path_for,
    build_archive_authentication,
    export_archive_authentication_file,
    verify_archive_authenticity,
)
from app.archive_signature import (
    MAX_SIGNATURE_CLOCK_SKEW,
    ArchiveSignaturePayload,
    archive_signature_path_for,
    export_archive_signature_file,
    sign_archive,
    verify_archive_signature,
)
from app.audit_report import validate_audit_report_json
from app.authentication_trust import (
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    ensure_key_trusted_for_verification,
    select_signing_key,
)
from app.exceptions import (
    AuthenticationFilenameMismatchError,
    ChecksumFilenameMismatchError,
    DuplicateReportArchiveMemberError,
    IncompleteReportBundleError,
    InvalidReportArchiveError,
    InvalidReportArchiveMemberError,
    InvalidReportArchivePathError,
    MissingReportArchiveMemberError,
    ReportArchiveDigestMismatchError,
    ReportArchiveExportError,
    ReportArchiveMetadataMismatchError,
    ReportArchiveReadError,
    ReportArchiveSizeLimitError,
    UnexpectedReportArchiveMemberError,
    UnsafeReportArchiveMemberError,
)
from app.report_authenticity import (
    HMAC_ALGORITHM,
    HMAC_PROTOCOL_VERSION,
    MAX_AUTHENTICATION_CLOCK_SKEW,
    authentication_path_for,
    calculate_report_hmac_bytes,
    parse_report_authentication,
)
from app.report_bundle import (
    REPORT_BUNDLE_MANIFEST_VERSION,
    manifest_path_for,
    validate_report_bundle_manifest_json,
    verify_report_bundle,
)
from app.report_integrity import (
    calculate_sha256,
    calculate_sha256_bytes,
    checksum_path_for,
    is_valid_sha256_digest,
    parse_report_checksum,
)
from app.signature_trust import (
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    RevokedSignatureKeyPolicy,
    ensure_private_key_trusted_for_signing,
)

ZIP_MEMBER_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_ARCHIVE_MEMBER_COUNT = 4
MAX_ARCHIVE_MEMBER_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100.0
COMPRESSION_RATIO_MINIMUM_SIZE = 4 * 1024
ZIP_MEMBER_MODE = 0o100600

_EXPORT_ERROR_MESSAGE = "Failed to export the audit report archive."
_READ_ERROR_MESSAGE = "Failed to read the audit report archive."
_PATH_ERROR_MESSAGE = "The audit report archive path is invalid."
_UNSAFE_MEMBER_MESSAGE = "The audit report archive contains an unsafe member."
_INVALID_ARCHIVE_MESSAGE = "The audit report archive is invalid."
_INVALID_MEMBER_MESSAGE = "The audit report archive member is invalid."
_DIGEST_MISMATCH_MESSAGE = "The audit report archive digest does not match."
_METADATA_MISMATCH_MESSAGE = "The audit report archive metadata is inconsistent."
_MISSING_MEMBER_MESSAGE = "The audit report archive is missing a required member."
_UNEXPECTED_MEMBER_MESSAGE = "The audit report archive contains an unexpected member."
_DUPLICATE_MEMBER_MESSAGE = "The audit report archive contains duplicate members."
_SIZE_LIMIT_MESSAGE = "The audit report archive exceeds configured size limits."


@dataclass(frozen=True)
class ReportArchiveExportResult:
    archive_filename: str
    archive_sha256: str
    member_count: int
    manifest_version: int


@dataclass(frozen=True)
class ReportArchiveVerificationResult:
    archive_format_version: int
    manifest_version: int
    report_schema_version: int
    authentication_protocol_version: int
    algorithm: str
    key_id: str
    authenticated_at: datetime
    report_filename: str
    archive_sha256: str
    member_count: int


@dataclass(frozen=True)
class AuthenticatedReportArchiveResult:
    archive_format_version: int
    archive_authentication_protocol_version: int
    archive_algorithm: str
    archive_key_id: str
    archive_authenticated_at: datetime
    archive_digest: str
    archive_sha256: str
    member_count: int
    manifest_version: int
    report_schema_version: int
    report_authentication_protocol_version: int
    report_algorithm: str
    report_key_id: str
    report_authenticated_at: datetime
    report_filename: str


@dataclass(frozen=True)
class SignedAuthenticatedReportArchiveResult:
    signature_algorithm: str
    signature_protocol_version: int
    signature_key_id: str
    signature_public_key_fingerprint: str
    signature_signed_at: datetime
    signature_archive_sha256: str
    archive_format_version: int
    archive_authentication_protocol_version: int
    archive_algorithm: str
    archive_key_id: str
    archive_authenticated_at: datetime
    archive_digest: str
    archive_sha256: str
    member_count: int
    manifest_version: int
    report_schema_version: int
    report_authentication_protocol_version: int
    report_algorithm: str
    report_key_id: str
    report_authenticated_at: datetime
    report_filename: str


def archive_path_for(report_path: Path) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    if report_path.suffix.lower() != ".json":
        raise InvalidReportArchivePathError(_PATH_ERROR_MESSAGE)
    return report_path.parent / f"{report_path.stem}.bundle.zip"


def validate_archive_member_name(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip():
        return False
    if value in {".", ".."}:
        return False
    if any(character in value for character in ("/", "\\", ":", "\0")):
        return False
    return Path(value).name == value


def expected_archive_members(report_filename: str) -> tuple[str, ...]:
    if not validate_archive_member_name(report_filename):
        raise InvalidReportArchivePathError(_PATH_ERROR_MESSAGE)
    if not report_filename.lower().endswith(".json"):
        raise InvalidReportArchivePathError(_PATH_ERROR_MESSAGE)
    return (
        report_filename,
        f"{report_filename}.sha256",
        f"{report_filename}.hmac",
        f"{report_filename}.manifest",
    )


def export_report_archive(
    *,
    report_path: Path,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> ReportArchiveExportResult:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a Path")
    if not isinstance(verification_time, datetime):
        raise TypeError("verification_time must be a datetime")
    _validate_archive_output_path(archive_path)

    bundle_result = verify_report_bundle(
        report_path=report_path,
        trust_store=trust_store,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    member_paths = (
        report_path,
        checksum_path_for(report_path),
        authentication_path_for(report_path),
        manifest_path_for(report_path),
    )
    member_names = expected_archive_members(report_path.name)
    member_bytes = tuple(_read_regular_file_bytes(path) for path in member_paths)

    temp_path: Path | None = None
    replaced = False
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=archive_path.parent,
            prefix=f".{archive_path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)

        with ZipFile(
            temp_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=False,
        ) as archive:
            for member_name, data in zip(member_names, member_bytes, strict=True):
                archive.writestr(_build_zip_info(member_name), data)

        with temp_path.open("r+b") as file:
            os.fsync(file.fileno())

        os.replace(temp_path, archive_path)
        replaced = True
    except (OSError, BadZipFile, LargeZipFile) as error:
        raise ReportArchiveExportError(_EXPORT_ERROR_MESSAGE) from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    return ReportArchiveExportResult(
        archive_filename=archive_path.name,
        archive_sha256=calculate_sha256(archive_path),
        member_count=MAX_ARCHIVE_MEMBER_COUNT,
        manifest_version=bundle_result.manifest_version,
    )


def verify_report_archive(
    *,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> ReportArchiveVerificationResult:
    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a Path")
    if not isinstance(trust_store, AuthenticationTrustStore):
        raise TypeError("trust_store must be an AuthenticationTrustStore")
    if not isinstance(verification_time, datetime):
        raise TypeError("verification_time must be a datetime")
    _ensure_archive_file(archive_path)
    if archive_path.stat().st_size > MAX_ARCHIVE_COMPRESSED_BYTES:
        raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)

    try:
        with ZipFile(archive_path, mode="r") as archive:
            infos = archive.infolist()
            _validate_archive_infos(infos)
            members = _read_archive_members(archive, infos)
    except (BadZipFile, LargeZipFile) as error:
        raise InvalidReportArchiveError(_INVALID_ARCHIVE_MESSAGE) from error
    except OSError as error:
        raise ReportArchiveReadError(_READ_ERROR_MESSAGE) from error

    manifest_name = _find_single_manifest_name(members)
    manifest_text = _decode_member_text(members[manifest_name])
    manifest = validate_report_bundle_manifest_json(manifest_text)
    expected_members = expected_archive_members(manifest.report.filename)
    actual_members = tuple(members.keys())
    _validate_expected_member_set(actual_members, expected_members)
    if manifest_name != f"{manifest.report.filename}.manifest":
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)

    report_bytes = members[manifest.report.filename]
    checksum_bytes = members[manifest.checksum.filename]
    authentication_bytes = members[manifest.authentication.filename]

    report_digest = calculate_sha256_bytes(report_bytes)
    checksum_digest = calculate_sha256_bytes(checksum_bytes)
    authentication_digest = calculate_sha256_bytes(authentication_bytes)
    _compare_digest(manifest.report.sha256, report_digest)
    _compare_digest(manifest.checksum.sha256, checksum_digest)
    _compare_digest(manifest.authentication.sha256, authentication_digest)

    report_text = _decode_member_text(report_bytes)
    checksum_text = _decode_member_text(checksum_bytes)
    authentication_text = _decode_member_text(authentication_bytes)

    report_payload = validate_audit_report_json(report_text)
    checksum = parse_report_checksum(checksum_text)
    authentication = parse_report_authentication(authentication_text)

    if checksum.filename != manifest.report.filename:
        raise ChecksumFilenameMismatchError("The checksum filename does not match the audit report.")
    if authentication.filename != manifest.report.filename:
        raise AuthenticationFilenameMismatchError(
            "The authentication filename does not match the audit report."
        )

    _compare_digest(checksum.digest, report_digest)

    key = trust_store.get_key(authentication.key_id)
    ensure_key_trusted_for_verification(
        key=key,
        authenticated_at=authentication.authenticated_at,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    actual_hmac = calculate_report_hmac_bytes(
        filename=manifest.report.filename,
        data=report_bytes,
        key=key,
        authenticated_at=authentication.authenticated_at,
    )
    _compare_digest(authentication.digest, actual_hmac)

    if report_payload.schema_version != manifest.report.schema_version:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authentication.algorithm != manifest.authentication.algorithm:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authentication.protocol_version != manifest.authentication.protocol_version:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authentication.key_id != manifest.authentication.key_id:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if authentication.authenticated_at != manifest.authentication.authenticated_at:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if manifest.manifest_version != REPORT_BUNDLE_MANIFEST_VERSION:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if manifest.authentication.algorithm != HMAC_ALGORITHM:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)
    if manifest.authentication.protocol_version != HMAC_PROTOCOL_VERSION:
        raise ReportArchiveMetadataMismatchError(_METADATA_MISMATCH_MESSAGE)

    return ReportArchiveVerificationResult(
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        manifest_version=manifest.manifest_version,
        report_schema_version=manifest.report.schema_version,
        authentication_protocol_version=manifest.authentication.protocol_version,
        algorithm=manifest.authentication.algorithm,
        key_id=manifest.authentication.key_id,
        authenticated_at=manifest.authentication.authenticated_at,
        report_filename=manifest.report.filename,
        archive_sha256=calculate_sha256(archive_path),
        member_count=len(members),
    )



def export_authenticated_report_archive(
    *,
    report_path: Path,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> tuple[ReportArchiveExportResult, ArchiveAuthentication]:
    signing_key = select_signing_key(
        trust_store=trust_store,
        authenticated_at=authenticated_at,
    )
    archive = export_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store,
        verification_time=authenticated_at,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    authentication = build_archive_authentication(
        archive_path=archive_path,
        key=signing_key,
        authenticated_at=authenticated_at,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )
    export_archive_authentication_file(
        path=archive_authentication_path_for(archive_path),
        authentication=authentication,
    )
    return archive, authentication


def verify_authenticated_report_archive(
    *,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> AuthenticatedReportArchiveResult:
    archive_authentication = verify_archive_authenticity(
        archive_path=archive_path,
        trust_store=trust_store,
        verification_time=verification_time,
        expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    archive = verify_report_archive(
        archive_path=archive_path,
        trust_store=trust_store,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    return AuthenticatedReportArchiveResult(
        archive_format_version=archive.archive_format_version,
        archive_authentication_protocol_version=archive_authentication.protocol_version,
        archive_algorithm=archive_authentication.algorithm,
        archive_key_id=archive_authentication.key_id,
        archive_authenticated_at=archive_authentication.authenticated_at,
        archive_digest=archive_authentication.digest,
        archive_sha256=archive.archive_sha256,
        member_count=archive.member_count,
        manifest_version=archive.manifest_version,
        report_schema_version=archive.report_schema_version,
        report_authentication_protocol_version=archive.authentication_protocol_version,
        report_algorithm=archive.algorithm,
        report_key_id=archive.key_id,
        report_authenticated_at=archive.authenticated_at,
        report_filename=archive.report_filename,
    )


def export_signed_authenticated_report_archive(
    *,
    report_path: Path,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
    signing_key: ArchiveSigningPrivateKey,
    signature_trust_store: ArchiveSignatureTrustStore,
    signed_at: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
) -> tuple[ReportArchiveExportResult, ArchiveAuthentication, ArchiveSignaturePayload]:
    ensure_private_key_trusted_for_signing(
        signing_key=signing_key,
        trust_store=signature_trust_store,
        signed_at=signed_at,
    )
    archive, archive_authentication = export_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store,
        authenticated_at=authenticated_at,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    signature = sign_archive(
        archive_path=archive_path,
        signing_key=signing_key,
        signed_at=signed_at,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )
    export_archive_signature_file(
        path=archive_signature_path_for(archive_path),
        signature=signature,
    )
    return archive, archive_authentication, signature


def verify_signed_authenticated_report_archive(
    *,
    archive_path: Path,
    trust_store: AuthenticationTrustStore,
    signature_trust_store: ArchiveSignatureTrustStore,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy = RevokedKeyPolicy.REJECT,
    revoked_signature_key_policy: RevokedSignatureKeyPolicy = RevokedSignatureKeyPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_AUTHENTICATION_CLOCK_SKEW,
    maximum_signature_clock_skew: timedelta = MAX_SIGNATURE_CLOCK_SKEW,
) -> SignedAuthenticatedReportArchiveResult:
    signature = verify_archive_signature(
        archive_path=archive_path,
        signature_trust_store=signature_trust_store,
        verification_time=verification_time,
        revoked_key_policy=revoked_signature_key_policy,
        maximum_clock_skew=maximum_signature_clock_skew,
    )
    archive = verify_authenticated_report_archive(
        archive_path=archive_path,
        trust_store=trust_store,
        verification_time=verification_time,
        revoked_key_policy=revoked_key_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    return SignedAuthenticatedReportArchiveResult(
        signature_algorithm=signature.algorithm,
        signature_protocol_version=signature.protocol_version,
        signature_key_id=signature.key_id,
        signature_public_key_fingerprint=signature.public_key_fingerprint,
        signature_signed_at=signature.signed_at,
        signature_archive_sha256=signature.archive_sha256,
        archive_format_version=archive.archive_format_version,
        archive_authentication_protocol_version=archive.archive_authentication_protocol_version,
        archive_algorithm=archive.archive_algorithm,
        archive_key_id=archive.archive_key_id,
        archive_authenticated_at=archive.archive_authenticated_at,
        archive_digest=archive.archive_digest,
        archive_sha256=archive.archive_sha256,
        member_count=archive.member_count,
        manifest_version=archive.manifest_version,
        report_schema_version=archive.report_schema_version,
        report_authentication_protocol_version=archive.report_authentication_protocol_version,
        report_algorithm=archive.report_algorithm,
        report_key_id=archive.report_key_id,
        report_authenticated_at=archive.report_authenticated_at,
        report_filename=archive.report_filename,
    )


def _validate_archive_output_path(path: Path) -> None:
    if not isinstance(path, Path):
        raise TypeError("archive_path must be a Path")
    if path.suffix.lower() != ".zip":
        raise InvalidReportArchivePathError(_PATH_ERROR_MESSAGE)
    if path.is_dir() or path.is_symlink():
        raise InvalidReportArchivePathError(_PATH_ERROR_MESSAGE)


def _build_zip_info(member_name: str) -> ZipInfo:
    if not validate_archive_member_name(member_name):
        raise UnsafeReportArchiveMemberError(_UNSAFE_MEMBER_MESSAGE)
    info = ZipInfo(member_name, ZIP_MEMBER_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = ZIP_MEMBER_MODE << 16
    return info


def _is_symlink_zip_info(info: ZipInfo) -> bool:
    if info.create_system != 3:
        return False
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _validate_zip_info(info: ZipInfo) -> None:
    if not validate_archive_member_name(info.filename):
        raise UnsafeReportArchiveMemberError(_UNSAFE_MEMBER_MESSAGE)
    if info.is_dir() or _is_symlink_zip_info(info):
        raise UnsafeReportArchiveMemberError(_UNSAFE_MEMBER_MESSAGE)
    if info.flag_bits & 0x1:
        raise UnsafeReportArchiveMemberError(_UNSAFE_MEMBER_MESSAGE)
    if info.file_size > MAX_ARCHIVE_MEMBER_UNCOMPRESSED_BYTES:
        raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)
    if info.compress_size > MAX_ARCHIVE_COMPRESSED_BYTES:
        raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)
    if info.file_size >= COMPRESSION_RATIO_MINIMUM_SIZE:
        if info.compress_size <= 0:
            raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)
        if info.file_size / info.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO:
            raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)


def _validate_archive_infos(infos: list[ZipInfo]) -> None:
    if len(infos) > MAX_ARCHIVE_MEMBER_COUNT:
        raise UnexpectedReportArchiveMemberError(_UNEXPECTED_MEMBER_MESSAGE)
    seen: set[str] = set()
    total_size = 0
    for info in infos:
        _validate_zip_info(info)
        if info.filename in seen:
            raise DuplicateReportArchiveMemberError(_DUPLICATE_MEMBER_MESSAGE)
        seen.add(info.filename)
        total_size += info.file_size
    if total_size > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
        raise ReportArchiveSizeLimitError(_SIZE_LIMIT_MESSAGE)


def _read_archive_members(archive: ZipFile, infos: list[ZipInfo]) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    for info in infos:
        try:
            members[info.filename] = archive.read(info)
        except (BadZipFile, RuntimeError, NotImplementedError, ValueError) as error:
            raise InvalidReportArchiveError(_INVALID_ARCHIVE_MESSAGE) from error
    return members


def _find_single_manifest_name(members: dict[str, bytes]) -> str:
    manifest_names = [name for name in members if name.lower().endswith(".manifest")]
    if len(manifest_names) != 1:
        raise MissingReportArchiveMemberError(_MISSING_MEMBER_MESSAGE)
    return manifest_names[0]


def _validate_expected_member_set(actual_members: tuple[str, ...], expected_members: tuple[str, ...]) -> None:
    actual_set = set(actual_members)
    expected_set = set(expected_members)
    if expected_set - actual_set:
        raise MissingReportArchiveMemberError(_MISSING_MEMBER_MESSAGE)
    if actual_set - expected_set:
        raise UnexpectedReportArchiveMemberError(_UNEXPECTED_MEMBER_MESSAGE)


def _decode_member_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidReportArchiveMemberError(_INVALID_MEMBER_MESSAGE) from error


def _compare_digest(expected: str, actual: str) -> None:
    if not is_valid_sha256_digest(expected) or not hmac.compare_digest(expected, actual):
        raise ReportArchiveDigestMismatchError(_DIGEST_MISMATCH_MESSAGE)


def _read_regular_file_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise IncompleteReportBundleError("The audit report bundle is incomplete.")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReportArchiveReadError(_READ_ERROR_MESSAGE) from error


def _ensure_archive_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ReportArchiveReadError(_READ_ERROR_MESSAGE)
