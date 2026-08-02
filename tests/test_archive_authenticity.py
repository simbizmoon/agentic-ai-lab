from __future__ import annotations

import hmac
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.archive_authenticity import (
    ARCHIVE_HMAC_ALGORITHM,
    ARCHIVE_HMAC_DOMAIN_SEPARATOR,
    ARCHIVE_HMAC_PROTOCOL_VERSION,
    REPORT_ARCHIVE_FORMAT_VERSION,
    ArchiveAuthentication,
    ArchiveAuthenticityResult,
    archive_authentication_path_for,
    build_archive_authentication,
    calculate_archive_hmac,
    calculate_archive_hmac_bytes,
    export_archive_authentication_file,
    format_archive_authentication,
    parse_archive_authentication,
    verify_archive_authenticity,
)
from app.authentication_trust import (
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    ArchiveAuthenticationExportError,
    ArchiveAuthenticationFilenameMismatchError,
    ArchiveAuthenticationFormatVersionMismatchError,
    ArchiveAuthenticationReadError,
    ArchiveAuthenticityMismatchError,
    InvalidArchiveAuthenticationFormatError,
    RejectedAuthenticationKeyError,
    UnknownAuthenticationKeyError,
)

SECRET = b"s" * 32
OTHER_SECRET = b"o" * 32
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
REVOKED_AT = datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
PRIVATE_TEXT = "PRIVATE-ARCHIVE-SECRET"


def key(
    *,
    key_id: str = "key-1",
    secret: bytes = SECRET,
    status: AuthenticationKeyStatus = AuthenticationKeyStatus.ACTIVE,
    revoked_at: datetime | None = None,
) -> TrustedAuthenticationKey:
    return TrustedAuthenticationKey(
        key_id=key_id,
        secret=secret,
        status=status,
        valid_from=datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
        revoked_at=revoked_at,
    )


def trust_store(*keys: TrustedAuthenticationKey) -> AuthenticationTrustStore:
    return AuthenticationTrustStore(keys=keys or (key(),))


def archive_file(tmp_path: Path, data: bytes = b"zip-bytes") -> Path:
    path = tmp_path / "audit-report.bundle.zip"
    path.write_bytes(data)
    return path


def export_sidecar(path: Path, *, signing_key: TrustedAuthenticationKey | None = None) -> ArchiveAuthentication:
    authentication = build_archive_authentication(
        archive_path=path,
        key=signing_key or key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )
    export_archive_authentication_file(
        path=archive_authentication_path_for(path),
        authentication=authentication,
    )
    return authentication


def test_archive_authentication_path_for_uses_same_parent_and_hmac_suffix(tmp_path: Path) -> None:
    path = archive_authentication_path_for(tmp_path / "audit-report.bundle.zip")

    assert path.parent == tmp_path
    assert path.name == "audit-report.bundle.zip.hmac"


@pytest.mark.parametrize("path", ["report.zip", "report.bundle.txt", 123])
def test_archive_authentication_path_for_rejects_invalid_archive_path(path: object) -> None:
    with pytest.raises((InvalidArchiveAuthenticationFormatError, TypeError)):
        archive_authentication_path_for(path)  # type: ignore[arg-type]


def test_calculate_archive_hmac_bytes_matches_path_based_calculation(tmp_path: Path) -> None:
    path = archive_file(tmp_path, b"archive bytes")

    assert calculate_archive_hmac(
        archive_path=path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    ) == calculate_archive_hmac_bytes(
        filename=path.name,
        data=b"archive bytes",
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )


@pytest.mark.parametrize(
    "data, filename, secret, authenticated_at, version",
    [
        (b"changed", "audit-report.bundle.zip", SECRET, AUTHENTICATED_AT, REPORT_ARCHIVE_FORMAT_VERSION),
        (b"archive bytes", "other.bundle.zip", SECRET, AUTHENTICATED_AT, REPORT_ARCHIVE_FORMAT_VERSION),
        (b"archive bytes", "audit-report.bundle.zip", OTHER_SECRET, AUTHENTICATED_AT, REPORT_ARCHIVE_FORMAT_VERSION),
        (b"archive bytes", "audit-report.bundle.zip", SECRET, datetime(2026, 8, 2, 0, 1, tzinfo=UTC), REPORT_ARCHIVE_FORMAT_VERSION),
        (b"archive bytes", "audit-report.bundle.zip", SECRET, AUTHENTICATED_AT, 2),
    ],
)
def test_archive_hmac_changes_when_authenticated_inputs_change(
    data: bytes,
    filename: str,
    secret: bytes,
    authenticated_at: datetime,
    version: int,
) -> None:
    baseline = calculate_archive_hmac_bytes(
        filename="audit-report.bundle.zip",
        data=b"archive bytes",
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )

    changed = calculate_archive_hmac_bytes(
        filename=filename,
        data=data,
        key=key(secret=secret),
        authenticated_at=authenticated_at,
        archive_format_version=version,
    )

    assert changed != baseline


def test_archive_hmac_uses_domain_separator_and_metadata() -> None:
    digest = hmac.new(SECRET, digestmod="sha256")
    digest.update(ARCHIVE_HMAC_DOMAIN_SEPARATOR)
    digest.update(b"\0")
    digest.update(b"key-1")
    digest.update(b"\0")
    digest.update(AUTHENTICATED_AT.isoformat().encode("ascii"))
    digest.update(b"\0")
    digest.update(b"audit-report.bundle.zip")
    digest.update(b"\0")
    digest.update(str(REPORT_ARCHIVE_FORMAT_VERSION).encode("ascii"))
    digest.update(b"\0")
    digest.update(b"archive bytes")

    assert calculate_archive_hmac_bytes(
        filename="audit-report.bundle.zip",
        data=b"archive bytes",
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    ) == digest.hexdigest()


def test_calculate_archive_hmac_rejects_missing_directory_and_symlink(tmp_path: Path) -> None:
    with pytest.raises(ArchiveAuthenticationReadError):
        calculate_archive_hmac(
            archive_path=tmp_path / "missing.bundle.zip",
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
            archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )

    with pytest.raises(ArchiveAuthenticationReadError):
        calculate_archive_hmac(
            archive_path=tmp_path,
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
            archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )


def test_calculate_archive_hmac_rejects_non_bytes() -> None:
    with pytest.raises(TypeError):
        calculate_archive_hmac_bytes(
            filename="audit-report.bundle.zip",
            data=bytearray(b"data"),  # type: ignore[arg-type]
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
            archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )


def test_format_and_parse_archive_authentication_round_trip(tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    authentication = build_archive_authentication(
        archive_path=path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )

    text = format_archive_authentication(authentication)
    parsed = parse_archive_authentication(text)

    assert text.endswith("\n")
    assert text.count("  ") == 5
    assert parsed == authentication


@pytest.mark.parametrize(
    "text",
    [
        "bad  1  key-1  2026-08-02T00:00:00+00:00  " + "0" * 64 + "  audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  2  key-1  2026-08-02T00:00:00+00:00  " + "0" * 64 + "  audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  1  bad key  2026-08-02T00:00:00+00:00  " + "0" * 64 + "  audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  1  key-1  2026-08-02T00:00:00  " + "0" * 64 + "  audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  1  key-1  2026-08-02T00:00:00+00:00  " + "A" * 64 + "  audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  1  key-1  2026-08-02T00:00:00+00:00  " + "0" * 64 + "  ../audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1 key-1 2026-08-02T00:00:00+00:00 " + "0" * 64 + " audit-report.bundle.zip\n",
        "archive-hmac-sha256-v1  1  key-1  2026-08-02T00:00:00+00:00  " + "0" * 64 + "  audit-report.bundle.zip\nextra\n",
    ],
)
def test_parse_archive_authentication_rejects_invalid_text(text: str) -> None:
    with pytest.raises(InvalidArchiveAuthenticationFormatError) as exc_info:
        parse_archive_authentication(text)

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_export_archive_authentication_file_is_atomic(tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    authentication = export_sidecar(path)
    sidecar = archive_authentication_path_for(path)

    assert sidecar.read_text(encoding="utf-8") == format_archive_authentication(authentication)
    assert not list(tmp_path.glob("*.tmp"))


def test_export_archive_authentication_rejects_invalid_target(tmp_path: Path) -> None:
    authentication = build_archive_authentication(
        archive_path=archive_file(tmp_path),
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
        archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )

    with pytest.raises(ArchiveAuthenticationExportError):
        export_archive_authentication_file(path=tmp_path / "bad.hmac", authentication=authentication)


def test_verify_archive_authenticity_success(tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    export_sidecar(path)

    result = verify_archive_authenticity(
        archive_path=path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
        expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    )

    assert isinstance(result, ArchiveAuthenticityResult)
    assert result.algorithm == ARCHIVE_HMAC_ALGORITHM
    assert result.protocol_version == ARCHIVE_HMAC_PROTOCOL_VERSION
    assert result.archive_format_version == REPORT_ARCHIVE_FORMAT_VERSION
    assert result.filename == path.name


def test_verify_archive_authenticity_detects_filename_version_and_digest_errors(tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    authentication = export_sidecar(path)
    sidecar = archive_authentication_path_for(path)

    sidecar.write_text(
        format_archive_authentication(
            ArchiveAuthentication(
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                archive_format_version=authentication.archive_format_version,
                key_id=authentication.key_id,
                authenticated_at=authentication.authenticated_at,
                digest=authentication.digest,
                filename="other.bundle.zip",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArchiveAuthenticationFilenameMismatchError):
        verify_archive_authenticity(
            archive_path=path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )

    export_sidecar(path)
    with pytest.raises(ArchiveAuthenticationFormatVersionMismatchError):
        verify_archive_authenticity(
            archive_path=path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
            expected_archive_format_version=2,
        )

    export_sidecar(path)
    path.write_bytes(b"changed")
    with pytest.raises(ArchiveAuthenticityMismatchError):
        verify_archive_authenticity(
            archive_path=path,
            trust_store=trust_store(),
            verification_time=VERIFICATION_TIME,
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )


def test_verify_archive_authenticity_uses_sidecar_key_and_trust_policy(tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    old_key = key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_AT)
    export_sidecar(path, signing_key=old_key)

    with pytest.raises(RejectedAuthenticationKeyError):
        verify_archive_authenticity(
            archive_path=path,
            trust_store=trust_store(old_key),
            verification_time=VERIFICATION_TIME,
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        )

    assert verify_archive_authenticity(
        archive_path=path,
        trust_store=trust_store(old_key),
        verification_time=VERIFICATION_TIME,
        expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
        revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
    ).key_id == old_key.key_id

    with pytest.raises(UnknownAuthenticationKeyError):
        verify_archive_authenticity(
            archive_path=path,
            trust_store=trust_store(key(key_id="other-key")),
            verification_time=VERIFICATION_TIME,
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
            revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
        )


def test_verify_archive_authenticity_does_not_open_zip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = archive_file(tmp_path)
    export_sidecar(path)

    def fail_zip(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZIP parsing must not run")

    monkeypatch.setattr("zipfile.ZipFile", fail_zip)

    assert verify_archive_authenticity(
        archive_path=path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
        expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
    ).digest
