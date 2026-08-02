from __future__ import annotations

import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import report_archive
from app.archive_authenticity import archive_authentication_path_for
from app.archive_signature import archive_signature_path_for
from app.authentication_trust import (
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    ArchiveAuthenticityMismatchError,
    ArchiveSignatureArchiveDigestMismatchError,
    ArchiveSignatureExportError,
    AuthenticationFromFutureError,
    DuplicateReportArchiveMemberError,
    IncompleteReportBundleError,
    InvalidReportArchiveError,
    InvalidReportArchiveMemberError,
    InvalidReportArchivePathError,
    MissingReportArchiveMemberError,
    RejectedAuthenticationKeyError,
    ReportArchiveDigestMismatchError,
    ReportArchiveExportError,
    ReportArchiveReadError,
    ReportArchiveSizeLimitError,
    ReportBundleManifestValidationError,
    SigningKeyManifestDigestMismatchError,
    UnexpectedReportArchiveMemberError,
    UnsafeReportArchiveMemberError,
)
from app.manifest_trust_state import ManifestTrustStateMode, load_manifest_trust_state
from app.report_archive import (
    MAX_ARCHIVE_MEMBER_COUNT,
    REPORT_ARCHIVE_FORMAT_VERSION,
    ZIP_MEMBER_MODE,
    ZIP_MEMBER_TIMESTAMP,
    AuthenticatedReportArchiveResult,
    ReportArchiveExportResult,
    ReportArchiveVerificationResult,
    SignedAuthenticatedReportArchiveResult,
    archive_path_for,
    expected_archive_members,
    export_authenticated_report_archive,
    export_report_archive,
    export_signed_authenticated_report_archive,
    export_signed_authenticated_report_archive_with_manifest,
    validate_archive_member_name,
    verify_authenticated_report_archive,
    verify_report_archive,
    verify_signed_authenticated_report_archive,
    verify_signed_authenticated_report_archive_with_manifest,
    verify_signed_authenticated_report_archive_with_manifest_state,
)
from app.report_authenticity import HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION
from app.report_bundle import manifest_path_for
from app.report_export import export_json_report_bundle
from app.report_integrity import checksum_path_for, is_valid_sha256_digest
from app.root_signature_trust import (
    RootSigningPrivateKey,
    TrustedRootSigningPublicKey,
)
from app.root_signature_trust import (
    fingerprint_public_key as root_fingerprint_public_key,
)
from app.signature_trust import (
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    SignatureKeyStatus,
    TrustedArchiveSigningPublicKey,
    fingerprint_public_key,
)
from app.signing_key_manifest import (
    VerifiedSigningKeyManifest,
    build_signing_key_manifest,
    sign_signing_key_manifest,
    signing_key_manifest_signature_path_for,
    verify_signing_key_manifest,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
SECRET = b"s" * 32
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
REVOKED_AT = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
PRIVATE_TEXT = "PRIVATE-ARCHIVE-ERROR"


def valid_json_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def key(
    *,
    status: AuthenticationKeyStatus = AuthenticationKeyStatus.ACTIVE,
    revoked_at: datetime | None = None,
) -> TrustedAuthenticationKey:
    return TrustedAuthenticationKey(
        key_id="key-1",
        secret=SECRET,
        status=status,
        valid_from=datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
        revoked_at=revoked_at,
    )


def trust_store(*keys: TrustedAuthenticationKey) -> AuthenticationTrustStore:
    return AuthenticationTrustStore(keys=keys or (key(),))


def export_bundle(tmp_path: Path) -> Path:
    report_path = tmp_path / "audit-report.json"
    export_json_report_bundle(
        path=report_path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )
    return report_path


def export_archive(tmp_path: Path) -> tuple[Path, Path, ReportArchiveExportResult]:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    result = export_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )
    return report_path, archive_path, result


def read_zip_members(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def write_zip(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in members.items():
            info = ZipInfo(name, ZIP_MEMBER_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ZIP_MEMBER_MODE << 16
            archive.writestr(info, data)


@pytest.mark.parametrize("value", ["report.json", "report.json.sha256", "report.json.hmac", "report.json.manifest"])
def test_validate_archive_member_name_accepts_safe_names(value: str) -> None:
    assert validate_archive_member_name(value) is True


@pytest.mark.parametrize("value", ["", " report.json", "report.json ", "../report.json", "/report.json", "C:report.json", "a/b", r"a\b", "a\0b", ".", "..", 123])
def test_validate_archive_member_name_rejects_unsafe_names(value: object) -> None:
    assert validate_archive_member_name(value) is False


def test_archive_path_for_uses_bundle_zip_suffix(tmp_path: Path) -> None:
    path = archive_path_for(tmp_path / "audit-report.json")

    assert path.parent == tmp_path
    assert path.name == "audit-report.bundle.zip"


def test_archive_path_for_rejects_non_json(tmp_path: Path) -> None:
    with pytest.raises(InvalidReportArchivePathError):
        archive_path_for(tmp_path / "audit-report.txt")


def test_expected_archive_members_returns_fixed_order() -> None:
    assert expected_archive_members("audit-report.json") == (
        "audit-report.json",
        "audit-report.json.sha256",
        "audit-report.json.hmac",
        "audit-report.json.manifest",
    )


def test_export_report_archive_creates_zip_with_four_members(tmp_path: Path) -> None:
    _, archive_path, result = export_archive(tmp_path)

    assert archive_path.is_file()
    assert isinstance(result, ReportArchiveExportResult)
    assert result.member_count == MAX_ARCHIVE_MEMBER_COUNT
    assert result.manifest_version == 1
    assert is_valid_sha256_digest(result.archive_sha256)


def test_export_report_archive_member_metadata_is_reproducible(tmp_path: Path) -> None:
    report_path, archive_path, _ = export_archive(tmp_path)

    with ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()

    assert [info.filename for info in infos] == list(expected_archive_members(report_path.name))
    assert all(info.date_time == ZIP_MEMBER_TIMESTAMP for info in infos)
    assert all(info.compress_type == ZIP_DEFLATED for info in infos)
    assert all(info.create_system == 3 for info in infos)
    assert all((info.external_attr >> 16) == ZIP_MEMBER_MODE for info in infos)


def test_export_report_archive_preserves_original_bundle_files(tmp_path: Path) -> None:
    report_path, archive_path, _ = export_archive(tmp_path)

    assert report_path.exists()
    assert checksum_path_for(report_path).exists()
    assert report_path.with_name(f"{report_path.name}.hmac").exists()
    assert manifest_path_for(report_path).exists()
    assert archive_path.exists()


def test_export_report_archive_calls_fsync_and_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
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

    monkeypatch.setattr(report_archive.os, "fsync", recording_fsync)
    monkeypatch.setattr(report_archive.os, "replace", recording_replace)

    export_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )

    assert fsync_calls
    assert replace_calls[-1][1] == archive_path


def test_export_report_archive_replace_failure_preserves_existing_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    archive_path.write_bytes(b"existing")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_TEXT)

    monkeypatch.setattr(report_archive.os, "replace", fail_replace)

    with pytest.raises(ReportArchiveExportError) as exc_info:
        export_report_archive(
            report_path=report_path,
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )

    assert archive_path.read_bytes() == b"existing"
    assert not list(tmp_path.glob("*.tmp"))
    assert PRIVATE_TEXT not in str(exc_info.value)


def test_export_report_archive_does_not_create_zip_when_bundle_invalid(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    checksum_path_for(report_path).unlink()

    with pytest.raises(IncompleteReportBundleError):
        export_report_archive(
            report_path=report_path,
            archive_path=archive_path_for(report_path),
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )

    assert not archive_path_for(report_path).exists()


def test_verify_report_archive_success(tmp_path: Path) -> None:
    _, archive_path, _ = export_archive(tmp_path)

    result = verify_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )

    assert isinstance(result, ReportArchiveVerificationResult)
    assert result.archive_format_version == REPORT_ARCHIVE_FORMAT_VERSION
    assert result.manifest_version == 1
    assert result.report_schema_version == 1
    assert result.authentication_protocol_version == HMAC_PROTOCOL_VERSION
    assert result.algorithm == HMAC_ALGORITHM
    assert result.key_id == "key-1"
    assert result.authenticated_at == AUTHENTICATED_AT
    assert result.report_filename == "audit-report.json"
    assert result.member_count == 4
    assert is_valid_sha256_digest(result.archive_sha256)


def test_verify_report_archive_succeeds_without_external_bundle_files(tmp_path: Path) -> None:
    report_path, archive_path, _ = export_archive(tmp_path)
    for path in (
        report_path,
        checksum_path_for(report_path),
        report_path.with_name(f"{report_path.name}.hmac"),
        manifest_path_for(report_path),
    ):
        path.unlink()

    assert verify_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    ).member_count == 4


def test_verify_report_archive_does_not_extract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, archive_path, _ = export_archive(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("extract must not be called")

    monkeypatch.setattr(ZipFile, "extract", forbidden)
    monkeypatch.setattr(ZipFile, "extractall", forbidden)

    verify_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )


@pytest.mark.parametrize("member", ["json", "checksum", "hmac", "manifest"])
def test_verify_report_archive_detects_member_tampering(tmp_path: Path, member: str) -> None:
    report_path, archive_path, _ = export_archive(tmp_path)
    members = read_zip_members(archive_path)
    names = expected_archive_members(report_path.name)
    index = {"json": 0, "checksum": 1, "hmac": 2, "manifest": 3}[member]
    members[names[index]] = members[names[index]] + b"x"
    write_zip(archive_path, members)

    with pytest.raises((ReportArchiveDigestMismatchError, InvalidReportArchiveError, InvalidReportArchiveMemberError, ReportBundleManifestValidationError)):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_duplicate_member(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    members = expected_archive_members(report_path.name)
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(members[0], b"one")
        archive.writestr(members[0], b"two")

    with pytest.raises(DuplicateReportArchiveMemberError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


@pytest.mark.parametrize("name", ["extra.txt", "nested/report.json", r"nested\report.json", "../report.json", "/report.json", "C:report.json"])
def test_verify_report_archive_rejects_unexpected_or_unsafe_members(tmp_path: Path, name: str) -> None:
    _, archive_path, _ = export_archive(tmp_path)
    members = read_zip_members(archive_path)
    members[name] = b"x"
    write_zip(archive_path, members)

    with pytest.raises((UnexpectedReportArchiveMemberError, UnsafeReportArchiveMemberError)):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_missing_member(tmp_path: Path) -> None:
    report_path, archive_path, _ = export_archive(tmp_path)
    members = read_zip_members(archive_path)
    members.pop(expected_archive_members(report_path.name)[1])
    write_zip(archive_path, members)

    with pytest.raises(MissingReportArchiveMemberError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_directory_member(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("directory/", b"")

    with pytest.raises(UnsafeReportArchiveMemberError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_symlink_member(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    info = ZipInfo("audit-report.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(info, b"target")

    with pytest.raises(UnsafeReportArchiveMemberError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_encrypted_flag(tmp_path: Path) -> None:
    info = ZipInfo("audit-report.json")
    info.flag_bits |= 0x1

    with pytest.raises(UnsafeReportArchiveMemberError):
        report_archive._validate_zip_info(info)


def test_verify_report_archive_rejects_size_limits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, archive_path, _ = export_archive(tmp_path)
    monkeypatch.setattr(report_archive, "MAX_ARCHIVE_COMPRESSED_BYTES", 1)

    with pytest.raises(ReportArchiveSizeLimitError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_compression_ratio() -> None:
    info = ZipInfo("audit-report.json")
    info.file_size = 4096
    info.compress_size = 1

    with pytest.raises(ReportArchiveSizeLimitError):
        report_archive._validate_zip_info(info)


def test_verify_report_archive_rejects_bad_zip(tmp_path: Path) -> None:
    archive_path = tmp_path / "audit-report.bundle.zip"
    archive_path.write_bytes(b"not a zip")

    with pytest.raises(InvalidReportArchiveError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_missing_archive(tmp_path: Path) -> None:
    with pytest.raises(ReportArchiveReadError):
        verify_report_archive(
            archive_path=tmp_path / "missing.zip",
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_rejects_revoked_key_by_default(tmp_path: Path) -> None:
    report_path = tmp_path / "audit-report.json"
    active_store = trust_store(key())
    revoked_store = trust_store(key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_AT))
    export_json_report_bundle(
        path=report_path,
        json_text=valid_json_text(),
        trust_store=active_store,
        authenticated_at=AUTHENTICATED_AT,
    )
    archive_path = archive_path_for(report_path)
    export_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=active_store,
        verification_time=AUTHENTICATED_AT,
    )

    with pytest.raises(RejectedAuthenticationKeyError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=revoked_store,
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_archive_allows_pre_revocation_policy(tmp_path: Path) -> None:
    report_path = tmp_path / "audit-report.json"
    active_store = trust_store(key())
    revoked_store = trust_store(key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_AT))
    export_json_report_bundle(
        path=report_path,
        json_text=valid_json_text(),
        trust_store=active_store,
        authenticated_at=AUTHENTICATED_AT,
    )
    archive_path = archive_path_for(report_path)
    export_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=active_store,
        verification_time=AUTHENTICATED_AT,
    )

    result = verify_report_archive(
        archive_path=archive_path,
        trust_store=revoked_store,
        verification_time=VERIFICATION_TIME,
        revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
    )

    assert result.key_id == "key-1"


def test_verify_report_archive_blocks_future_authentication(tmp_path: Path) -> None:
    _, archive_path, _ = export_archive(tmp_path)

    with pytest.raises(AuthenticationFromFutureError):
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=AUTHENTICATED_AT - timedelta(minutes=6),
        )


def test_verify_report_archive_uses_compare_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, archive_path, _ = export_archive(tmp_path)
    calls: list[tuple[str, str]] = []
    original = report_archive.hmac.compare_digest

    def recording_compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(report_archive.hmac, "compare_digest", recording_compare)

    verify_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )

    assert calls


def test_errors_do_not_expose_secret_member_or_digest(tmp_path: Path) -> None:
    archive_path = tmp_path / "PRIVATE-ARCHIVE-ERROR.bundle.zip"
    archive_path.write_bytes(b"not a zip")

    with pytest.raises(InvalidReportArchiveError) as exc_info:
        verify_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )

    message = str(exc_info.value)
    assert PRIVATE_TEXT not in message
    assert SECRET.decode("ascii") not in message
    assert "audit-report.json" not in message
    assert "a" * 64 not in message



def test_export_authenticated_report_archive_creates_archive_hmac(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)

    archive, authentication = export_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert isinstance(archive, ReportArchiveExportResult)
    assert authentication.key_id == "key-1"
    assert authentication.authenticated_at == AUTHENTICATED_AT
    assert archive_authentication_path_for(archive_path).is_file()


def test_verify_authenticated_report_archive_success(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    export_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    result = verify_authenticated_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )

    assert isinstance(result, AuthenticatedReportArchiveResult)
    assert result.archive_authentication_protocol_version == 1
    assert result.archive_key_id == "key-1"
    assert result.archive_authenticated_at == AUTHENTICATED_AT
    assert result.report_authentication_protocol_version == HMAC_PROTOCOL_VERSION
    assert result.report_key_id == "key-1"
    assert result.member_count == MAX_ARCHIVE_MEMBER_COUNT


def test_verify_authenticated_report_archive_checks_hmac_before_zip_parser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    export_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )
    archive_path.write_bytes(b"changed")

    def fail_zip_verify(**kwargs: object) -> None:
        raise AssertionError("internal archive verification must not run")

    monkeypatch.setattr(report_archive, "verify_report_archive", fail_zip_verify)

    with pytest.raises(ArchiveAuthenticityMismatchError):
        verify_authenticated_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
        )


def test_export_authenticated_report_archive_keeps_zip_when_hmac_export_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)

    def fail_export(**kwargs: object) -> None:
        raise RuntimeError(PRIVATE_TEXT)

    monkeypatch.setattr(report_archive, "export_archive_authentication_file", fail_export)

    with pytest.raises(RuntimeError) as exc_info:
        export_authenticated_report_archive(
            report_path=report_path,
            archive_path=archive_path,
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
        )

    assert archive_path.exists()
    assert PRIVATE_TEXT in str(exc_info.value)


def signature_private_bytes() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def signature_public_bytes(secret: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def signature_key(key_id: str = "sig-key") -> ArchiveSigningPrivateKey:
    secret = signature_private_bytes()
    public = signature_public_bytes(secret)
    return ArchiveSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=secret,
        public_key_bytes=public,
        public_key_fingerprint=fingerprint_public_key(public),
    )


def signature_store(signing_key: ArchiveSigningPrivateKey) -> ArchiveSignatureTrustStore:
    return ArchiveSignatureTrustStore(
        keys=(
            TrustedArchiveSigningPublicKey(
                key_id=signing_key.key_id,
                public_key_bytes=signing_key.public_key_bytes,
                public_key_fingerprint=signing_key.public_key_fingerprint,
                status=SignatureKeyStatus.ACTIVE,
                valid_from=datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
            ),
        )
    )


def test_export_signed_authenticated_report_archive_creates_signature(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()

    archive, archive_authentication, signature = export_signed_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        signature_trust_store=signature_store(signing_key),
        signed_at=AUTHENTICATED_AT,
    )

    assert isinstance(archive, ReportArchiveExportResult)
    assert archive_authentication.key_id == "key-1"
    assert signature.key_id == signing_key.key_id
    assert archive_signature_path_for(archive_path).is_file()
    assert archive_path.exists()


def test_verify_signed_authenticated_report_archive_returns_combined_result(tmp_path: Path) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    export_signed_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        signature_trust_store=signature_store(signing_key),
        signed_at=AUTHENTICATED_AT,
    )

    result = verify_signed_authenticated_report_archive(
        archive_path=archive_path,
        trust_store=trust_store(),
        signature_trust_store=signature_store(signing_key),
        verification_time=VERIFICATION_TIME,
    )

    assert isinstance(result, SignedAuthenticatedReportArchiveResult)
    assert result.signature_key_id == signing_key.key_id
    assert result.archive_key_id == "key-1"
    assert result.report_key_id == "key-1"
    assert result.signature_signed_at == AUTHENTICATED_AT


def test_verify_signed_authenticated_report_archive_checks_signature_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    export_signed_authenticated_report_archive(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        signature_trust_store=signature_store(signing_key),
        signed_at=AUTHENTICATED_AT,
    )
    archive_path.write_bytes(b"tampered")

    def fail_internal_verify(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("internal archive verification should not run")

    monkeypatch.setattr(report_archive, "verify_authenticated_report_archive", fail_internal_verify)

    with pytest.raises(ArchiveSignatureArchiveDigestMismatchError):
        verify_signed_authenticated_report_archive(
            archive_path=archive_path,
            trust_store=trust_store(),
            signature_trust_store=signature_store(signing_key),
            verification_time=VERIFICATION_TIME,
        )


def test_signed_archive_signature_export_failure_keeps_zip_and_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()

    def fail_export(*args: Any, **kwargs: Any) -> None:
        raise ArchiveSignatureExportError(PRIVATE_TEXT)

    monkeypatch.setattr(report_archive, "export_archive_signature_file", fail_export)

    with pytest.raises(ArchiveSignatureExportError):
        export_signed_authenticated_report_archive(
            report_path=report_path,
            archive_path=archive_path,
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
            signing_key=signing_key,
            signature_trust_store=signature_store(signing_key),
            signed_at=AUTHENTICATED_AT,
        )

    assert report_path.exists()
    assert checksum_path_for(report_path).exists()
    assert archive_authentication_path_for(archive_path).exists()
    assert archive_path.exists()


def root_pair_for_manifest() -> tuple[RootSigningPrivateKey, TrustedRootSigningPublicKey]:
    secret = signature_private_bytes()
    public = signature_public_bytes(secret)
    return (
        RootSigningPrivateKey("root-key", secret, public, root_fingerprint_public_key(public)),
        TrustedRootSigningPublicKey("root-key", public, root_fingerprint_public_key(public)),
    )


def verified_manifest_for_archive(
    tmp_path: Path,
    signing_key: ArchiveSigningPrivateKey,
) -> tuple[VerifiedSigningKeyManifest, Path, TrustedRootSigningPublicKey]:
    root_private, root_public = root_pair_for_manifest()
    manifest = build_signing_key_manifest(
        generation=1,
        issued_at=AUTHENTICATED_AT,
        valid_from=datetime(2026, 8, 1, tzinfo=UTC),
        valid_until=datetime(2030, 1, 1, tzinfo=UTC),
        root_public_key=root_public,
        keys=signature_store(signing_key).keys,
    )
    manifest_path = tmp_path / "signing-keys.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    signature = sign_signing_key_manifest(
        manifest=manifest,
        root_private_key=root_private,
        signed_at=AUTHENTICATED_AT,
        filename=manifest_path.name,
    )
    signing_key_manifest_signature_path_for(manifest_path).write_text(
        signature.model_dump_json(),
        encoding="utf-8",
    )
    return (
        verify_signing_key_manifest(
            manifest_path=manifest_path,
            root_public_key=root_public,
            verification_time=VERIFICATION_TIME,
        ),
        manifest_path,
        root_public,
    )


def test_export_signed_authenticated_report_archive_with_manifest_uses_verified_manifest(
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    verified_manifest, _manifest_path, _root_public = verified_manifest_for_archive(tmp_path, signing_key)

    archive, archive_authentication, signature = export_signed_authenticated_report_archive_with_manifest(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        verified_manifest=verified_manifest,
        signed_at=AUTHENTICATED_AT,
    )

    assert isinstance(archive, ReportArchiveExportResult)
    assert archive_authentication.key_id == "key-1"
    assert signature.key_id == verified_manifest.result.active_key_id
    assert archive_signature_path_for(archive_path).exists()


def test_verify_signed_authenticated_report_archive_with_manifest_blocks_before_signature(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    verified_manifest, manifest_path, root_public = verified_manifest_for_archive(tmp_path, signing_key)
    export_signed_authenticated_report_archive_with_manifest(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        verified_manifest=verified_manifest,
        signed_at=AUTHENTICATED_AT,
    )
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8").replace('"generation":1', '"generation":2'), encoding="utf-8")

    def fail_signature(*args: object, **kwargs: object) -> None:
        raise AssertionError("archive signature verification must not run")

    monkeypatch.setattr("app.report_archive.verify_signed_authenticated_report_archive", fail_signature)

    with pytest.raises(SigningKeyManifestDigestMismatchError):
        verify_signed_authenticated_report_archive_with_manifest(
            archive_path=archive_path,
            trust_store=trust_store(),
            manifest_path=manifest_path,
            root_public_key=root_public,
            verification_time=VERIFICATION_TIME,
        )


def test_verify_signed_authenticated_report_archive_with_manifest_state_updates_before_signature(
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    verified_manifest, manifest_path, root_public = verified_manifest_for_archive(tmp_path, signing_key)
    export_signed_authenticated_report_archive_with_manifest(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        verified_manifest=verified_manifest,
        signed_at=AUTHENTICATED_AT,
    )
    state_path = tmp_path / "manifest-state.json"

    result, verified, decision = verify_signed_authenticated_report_archive_with_manifest_state(
        archive_path=archive_path,
        trust_store=trust_store(),
        manifest_path=manifest_path,
        root_public_key=root_public,
        verification_time=VERIFICATION_TIME,
        state_path=state_path,
    )

    assert isinstance(result, SignedAuthenticatedReportArchiveResult)
    assert verified.result.generation == 1
    assert decision.state_updated is True
    assert load_manifest_trust_state(path=state_path).highest_generation == 1  # type: ignore[union-attr]


def test_verify_signed_authenticated_report_archive_with_manifest_state_read_only_blocks_rollback(
    tmp_path: Path,
) -> None:
    report_path = export_bundle(tmp_path)
    archive_path = archive_path_for(report_path)
    signing_key = signature_key()
    verified_manifest, manifest_path, root_public = verified_manifest_for_archive(tmp_path, signing_key)
    export_signed_authenticated_report_archive_with_manifest(
        report_path=report_path,
        archive_path=archive_path,
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
        signing_key=signing_key,
        verified_manifest=verified_manifest,
        signed_at=AUTHENTICATED_AT,
    )

    with pytest.raises(SigningKeyManifestDigestMismatchError):
        manifest_path.write_text(
            manifest_path.read_text(encoding="utf-8").replace('"generation":1', '"generation":2'),
            encoding="utf-8",
        )
        verify_signed_authenticated_report_archive_with_manifest_state(
            archive_path=archive_path,
            trust_store=trust_store(),
            manifest_path=manifest_path,
            root_public_key=root_public,
            verification_time=VERIFICATION_TIME,
            state_path=None,
            state_mode=ManifestTrustStateMode.READ_ONLY,
        )
