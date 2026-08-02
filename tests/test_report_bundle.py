from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app import report_bundle
from app.authentication_trust import (
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    AuditReportValidationError,
    AuthenticationFromFutureError,
    BundleReportFilenameMismatchError,
    IncompleteReportBundleError,
    RejectedAuthenticationKeyError,
    ReportBundleDigestMismatchError,
    ReportBundleExportError,
    ReportBundleManifestValidationError,
    ReportBundleMetadataMismatchError,
    ReportIntegrityMismatchError,
)
from app.report_authenticity import (
    HMAC_ALGORITHM,
    HMAC_PROTOCOL_VERSION,
    MAX_AUTHENTICATION_CLOCK_SKEW,
    ReportAuthentication,
    authentication_path_for,
    build_report_authentication,
    format_report_authentication,
)
from app.report_bundle import (
    REPORT_BUNDLE_MANIFEST_VERSION,
    REPORT_BUNDLE_TYPE,
    AuditReportBundleManifest,
    BundleAuthenticationEntry,
    BundleChecksumEntry,
    BundleReportEntry,
    ReportBundleVerificationResult,
    build_report_bundle_manifest,
    export_report_bundle_manifest,
    format_report_bundle_manifest,
    is_valid_bundle_filename,
    manifest_path_for,
    validate_report_bundle_manifest_json,
    verify_report_bundle,
)
from app.report_export import export_json_report_with_authentication
from app.report_integrity import (
    checksum_path_for,
    format_report_checksum,
    parse_report_checksum,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
SECRET = b"s" * 32
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
PRIVATE_TEXT = "PRIVATE-BUNDLE-ERROR"


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


def export_authenticated_report(tmp_path: Path) -> Path:
    report_path = tmp_path / "audit-report.json"
    export_json_report_with_authentication(
        path=report_path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )
    return report_path


def export_bundle(tmp_path: Path) -> tuple[Path, AuditReportBundleManifest]:
    report_path = export_authenticated_report(tmp_path)
    manifest = build_report_bundle_manifest(report_path=report_path)
    export_report_bundle_manifest(path=manifest_path_for(report_path), manifest=manifest)
    return report_path, manifest


@pytest.mark.parametrize("value", ["report.json", "report.json.sha256", "report.json.hmac"])
def test_valid_bundle_filename_accepts_basename(value: str) -> None:
    assert is_valid_bundle_filename(value) is True


@pytest.mark.parametrize("value", ["", " report.json", "report.json ", "a/b", r"a\b", ".", "..", 123])
def test_valid_bundle_filename_rejects_invalid_values(value: object) -> None:
    assert is_valid_bundle_filename(value) is False


def test_bundle_report_entry_accepts_valid_data() -> None:
    entry = BundleReportEntry(filename="report.json", schema_version=1, sha256="a" * 64)

    assert entry.filename == "report.json"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"filename": "report.txt", "schema_version": 1, "sha256": "a" * 64},
        {"filename": "nested/report.json", "schema_version": 1, "sha256": "a" * 64},
        {"filename": "report.json", "schema_version": 0, "sha256": "a" * 64},
        {"filename": "report.json", "schema_version": "1", "sha256": "a" * 64},
        {"filename": "report.json", "schema_version": 1, "sha256": "A" * 64},
    ],
)
def test_bundle_report_entry_rejects_invalid_data(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BundleReportEntry(**kwargs)


def test_bundle_checksum_entry_accepts_sha256_sidecar() -> None:
    entry = BundleChecksumEntry(filename="report.json.sha256", sha256="b" * 64)

    assert entry.filename == "report.json.sha256"


def test_bundle_checksum_entry_rejects_wrong_suffix() -> None:
    with pytest.raises(ValidationError):
        BundleChecksumEntry(filename="report.json", sha256="b" * 64)


def test_bundle_authentication_entry_accepts_v2_metadata() -> None:
    entry = BundleAuthenticationEntry(
        filename="report.json.hmac",
        sha256="c" * 64,
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id="key-1",
        authenticated_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
    )

    assert entry.authenticated_at == datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"filename": "report.json", "sha256": "c" * 64, "algorithm": HMAC_ALGORITHM, "protocol_version": 2, "key_id": "key-1", "authenticated_at": AUTHENTICATED_AT},
        {"filename": "report.json.hmac", "sha256": "C" * 64, "algorithm": HMAC_ALGORITHM, "protocol_version": 2, "key_id": "key-1", "authenticated_at": AUTHENTICATED_AT},
        {"filename": "report.json.hmac", "sha256": "c" * 64, "algorithm": "hmac-sha256", "protocol_version": 2, "key_id": "key-1", "authenticated_at": AUTHENTICATED_AT},
        {"filename": "report.json.hmac", "sha256": "c" * 64, "algorithm": HMAC_ALGORITHM, "protocol_version": 1, "key_id": "key-1", "authenticated_at": AUTHENTICATED_AT},
        {"filename": "report.json.hmac", "sha256": "c" * 64, "algorithm": HMAC_ALGORITHM, "protocol_version": 2, "key_id": "bad/key", "authenticated_at": AUTHENTICATED_AT},
        {"filename": "report.json.hmac", "sha256": "c" * 64, "algorithm": HMAC_ALGORITHM, "protocol_version": 2, "key_id": "key-1", "authenticated_at": datetime.fromisoformat("2026-08-02T00:00:00")},
    ],
)
def test_bundle_authentication_entry_rejects_invalid_data(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BundleAuthenticationEntry(**kwargs)


def test_manifest_accepts_related_filenames() -> None:
    manifest = AuditReportBundleManifest(
        manifest_version=REPORT_BUNDLE_MANIFEST_VERSION,
        bundle_type=REPORT_BUNDLE_TYPE,
        report=BundleReportEntry(filename="report.json", schema_version=1, sha256="a" * 64),
        checksum=BundleChecksumEntry(filename="report.json.sha256", sha256="b" * 64),
        authentication=BundleAuthenticationEntry(
            filename="report.json.hmac",
            sha256="c" * 64,
            algorithm=HMAC_ALGORITHM,
            protocol_version=HMAC_PROTOCOL_VERSION,
            key_id="key-1",
            authenticated_at=AUTHENTICATED_AT,
        ),
    )

    assert manifest.bundle_type == REPORT_BUNDLE_TYPE


@pytest.mark.parametrize(
    "field_name",
    ["manifest_version", "bundle_type", "checksum", "authentication"],
)
def test_manifest_rejects_contract_errors(field_name: str) -> None:
    data: dict[str, object] = {
        "manifest_version": REPORT_BUNDLE_MANIFEST_VERSION,
        "bundle_type": REPORT_BUNDLE_TYPE,
        "report": {"filename": "report.json", "schema_version": 1, "sha256": "a" * 64},
        "checksum": {"filename": "report.json.sha256", "sha256": "b" * 64},
        "authentication": {
            "filename": "report.json.hmac",
            "sha256": "c" * 64,
            "algorithm": HMAC_ALGORITHM,
            "protocol_version": HMAC_PROTOCOL_VERSION,
            "key_id": "key-1",
            "authenticated_at": AUTHENTICATED_AT,
        },
    }
    if field_name == "manifest_version":
        data[field_name] = 2
    elif field_name == "bundle_type":
        data[field_name] = "wrong"
    elif field_name == "checksum":
        data[field_name] = {"filename": "other.sha256", "sha256": "b" * 64}
    else:
        data[field_name] = {
            "filename": "other.hmac",
            "sha256": "c" * 64,
            "algorithm": HMAC_ALGORITHM,
            "protocol_version": HMAC_PROTOCOL_VERSION,
            "key_id": "key-1",
            "authenticated_at": AUTHENTICATED_AT,
        }

    with pytest.raises(ValidationError):
        AuditReportBundleManifest(**data)


def test_manifest_path_for_uses_same_parent_and_manifest_suffix(tmp_path: Path) -> None:
    path = manifest_path_for(tmp_path / "report.json")

    assert path.parent == tmp_path
    assert path.name == "report.json.manifest"


def test_manifest_path_for_rejects_non_path() -> None:
    with pytest.raises(TypeError):
        manifest_path_for("report.json")  # type: ignore[arg-type]


def test_build_report_bundle_manifest_reads_actual_metadata(tmp_path: Path) -> None:
    report_path = export_authenticated_report(tmp_path)

    manifest = build_report_bundle_manifest(report_path=report_path)

    assert manifest.report.filename == report_path.name
    assert manifest.report.schema_version == 1
    assert manifest.report.sha256
    assert manifest.checksum.filename == checksum_path_for(report_path).name
    assert manifest.authentication.filename == authentication_path_for(report_path).name
    assert manifest.authentication.protocol_version == HMAC_PROTOCOL_VERSION
    assert manifest.authentication.algorithm == HMAC_ALGORITHM
    assert manifest.authentication.key_id == "key-1"
    assert manifest.authentication.authenticated_at == AUTHENTICATED_AT


@pytest.mark.parametrize("remove_sidecar", ["report", "checksum", "hmac"])
def test_build_report_bundle_manifest_rejects_missing_files(tmp_path: Path, remove_sidecar: str) -> None:
    report_path = export_authenticated_report(tmp_path)
    target = {
        "report": report_path,
        "checksum": checksum_path_for(report_path),
        "hmac": authentication_path_for(report_path),
    }[remove_sidecar]
    target.unlink()

    with pytest.raises(IncompleteReportBundleError):
        build_report_bundle_manifest(report_path=report_path)


def test_build_report_bundle_manifest_rejects_checksum_filename_mismatch(tmp_path: Path) -> None:
    report_path = export_authenticated_report(tmp_path)
    checksum_path = checksum_path_for(report_path)
    checksum = parse_report_checksum(checksum_path.read_text(encoding="utf-8"))
    checksum_path.write_text(format_report_checksum(checksum).replace(report_path.name, "other.json"), encoding="utf-8")

    with pytest.raises(BundleReportFilenameMismatchError):
        build_report_bundle_manifest(report_path=report_path)


def test_build_report_bundle_manifest_rejects_checksum_digest_mismatch(tmp_path: Path) -> None:
    report_path = export_authenticated_report(tmp_path)
    checksum_path_for(report_path).write_text(f"{'0' * 64}  {report_path.name}\n", encoding="utf-8")

    with pytest.raises(ReportIntegrityMismatchError):
        build_report_bundle_manifest(report_path=report_path)


def test_build_report_bundle_manifest_rejects_hmac_filename_mismatch(tmp_path: Path) -> None:
    report_path = export_authenticated_report(tmp_path)
    authentication = build_report_authentication(report_path=report_path, key=key(), authenticated_at=AUTHENTICATED_AT)
    authentication_path_for(report_path).write_text(
        format_report_authentication(
            ReportAuthentication(
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                key_id=authentication.key_id,
                authenticated_at=authentication.authenticated_at,
                digest=authentication.digest,
                filename="other.json",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(BundleReportFilenameMismatchError):
        build_report_bundle_manifest(report_path=report_path)


def test_format_and_validate_manifest_round_trip(tmp_path: Path) -> None:
    _, manifest = export_bundle(tmp_path)

    text = format_report_bundle_manifest(manifest)
    payload = json.loads(text)
    parsed = validate_report_bundle_manifest_json(text)

    assert payload["manifest_version"] == REPORT_BUNDLE_MANIFEST_VERSION
    assert parsed == manifest


def test_validate_manifest_json_rejects_malformed_and_omits_text() -> None:
    with pytest.raises(ReportBundleManifestValidationError) as exc_info:
        validate_report_bundle_manifest_json(f"{{{PRIVATE_TEXT}")

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_export_report_bundle_manifest_writes_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, manifest = export_bundle(tmp_path)
    target = tmp_path / "custom.manifest"
    fsync_calls: list[int] = []
    replace_calls: list[tuple[Path, Path]] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def record_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        original_fsync(fd)

    def record_replace(source: Path, destination: Path) -> None:
        replace_calls.append((source, destination))
        original_replace(source, destination)

    monkeypatch.setattr(report_bundle.os, "fsync", record_fsync)
    monkeypatch.setattr(report_bundle.os, "replace", record_replace)

    export_report_bundle_manifest(path=target, manifest=manifest)

    assert target.read_text(encoding="utf-8").endswith("\n")
    assert not target.read_text(encoding="utf-8").endswith("\n\n")
    assert fsync_calls
    assert replace_calls and replace_calls[0][1] == target
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_export_report_bundle_manifest_preserves_existing_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, manifest = export_bundle(tmp_path)
    target = tmp_path / "custom.manifest"
    target.write_text("existing", encoding="utf-8")

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_TEXT)

    monkeypatch.setattr(report_bundle.os, "replace", broken_replace)

    with pytest.raises(ReportBundleExportError) as exc_info:
        export_report_bundle_manifest(path=target, manifest=manifest)

    assert target.read_text(encoding="utf-8") == "existing"
    assert PRIVATE_TEXT not in str(exc_info.value)
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_verify_report_bundle_success(tmp_path: Path) -> None:
    report_path, manifest = export_bundle(tmp_path)

    result = verify_report_bundle(
        report_path=report_path,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )

    assert isinstance(result, ReportBundleVerificationResult)
    assert result.manifest_version == manifest.manifest_version
    assert result.report_schema_version == 1
    assert result.authentication_protocol_version == HMAC_PROTOCOL_VERSION
    assert result.algorithm == HMAC_ALGORITHM
    assert result.key_id == "key-1"
    assert result.authenticated_at == AUTHENTICATED_AT
    assert result.report_filename == report_path.name


@pytest.mark.parametrize("remove_sidecar", ["report", "checksum", "hmac", "manifest"])
def test_verify_report_bundle_rejects_missing_files(tmp_path: Path, remove_sidecar: str) -> None:
    report_path, _ = export_bundle(tmp_path)
    target = {
        "report": report_path,
        "checksum": checksum_path_for(report_path),
        "hmac": authentication_path_for(report_path),
        "manifest": manifest_path_for(report_path),
    }[remove_sidecar]
    target.unlink()

    with pytest.raises(IncompleteReportBundleError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def mutate_manifest(report_path: Path, mutator: Any) -> None:
    manifest_path = manifest_path_for(report_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutator(payload)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_verify_report_bundle_rejects_malformed_manifest(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    manifest_path_for(report_path).write_text(f"{{{PRIVATE_TEXT}", encoding="utf-8")

    with pytest.raises(ReportBundleManifestValidationError) as exc_info:
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_verify_report_bundle_rejects_report_filename_mismatch(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)

    def mutate(payload: dict[str, Any]) -> None:
        payload["report"].update(filename="other.json")
        payload["checksum"].update(filename="other.json.sha256")
        payload["authentication"].update(filename="other.json.hmac")

    mutate_manifest(report_path, mutate)

    with pytest.raises(BundleReportFilenameMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


@pytest.mark.parametrize(
    "section",
    ["report", "checksum", "authentication"],
)
def test_verify_report_bundle_rejects_manifest_digest_mismatch(tmp_path: Path, section: str) -> None:
    report_path, _ = export_bundle(tmp_path)
    mutate_manifest(report_path, lambda payload: payload[section].update(sha256="0" * 64))

    with pytest.raises(ReportBundleDigestMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_rejects_json_tampering(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    report_path.write_text(valid_json_text().replace("gpt-5", "gpt-6"), encoding="utf-8")

    with pytest.raises(ReportBundleDigestMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_rejects_checksum_sidecar_tampering(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    checksum_path_for(report_path).write_text(f"{'0' * 64}  {report_path.name}\n", encoding="utf-8")

    with pytest.raises(ReportBundleDigestMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_rejects_hmac_sidecar_tampering(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    authentication_path_for(report_path).write_text("invalid", encoding="utf-8")

    with pytest.raises(ReportBundleDigestMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_rejects_metadata_mismatch_when_manifest_rebuilt_with_wrong_key(
    tmp_path: Path,
) -> None:
    report_path, manifest = export_bundle(tmp_path)
    replacement = manifest.model_copy(
        update={
            "authentication": manifest.authentication.model_copy(update={"key_id": "other-key"})
        }
    )
    # model_copy does not re-run validators; this simulates a syntactically valid but inconsistent manifest.
    manifest_path_for(report_path).write_text(format_report_bundle_manifest(replacement), encoding="utf-8")

    with pytest.raises(ReportBundleMetadataMismatchError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_rejects_revoked_key_by_default(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    revoked = key(status=AuthenticationKeyStatus.REVOKED, revoked_at=datetime(2100, 1, 1, tzinfo=UTC))

    with pytest.raises(RejectedAuthenticationKeyError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(revoked), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_allows_pre_revocation_policy(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    revoked = key(status=AuthenticationKeyStatus.REVOKED, revoked_at=datetime(2100, 1, 1, tzinfo=UTC))

    result = verify_report_bundle(
        report_path=report_path,
        trust_store=trust_store(revoked),
        verification_time=VERIFICATION_TIME,
        revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
    )

    assert result.key_id == "key-1"


def test_verify_report_bundle_blocks_future_authentication(tmp_path: Path) -> None:
    report_path = tmp_path / "audit-report.json"
    future_time = VERIFICATION_TIME + MAX_AUTHENTICATION_CLOCK_SKEW + timedelta(seconds=1)
    export_json_report_with_authentication(
        path=report_path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=future_time,
    )
    manifest = build_report_bundle_manifest(report_path=report_path)
    export_report_bundle_manifest(path=manifest_path_for(report_path), manifest=manifest)

    with pytest.raises(AuthenticationFromFutureError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_revalidates_json_contract(tmp_path: Path) -> None:
    report_path, manifest = export_bundle(tmp_path)
    report_path.write_text('{"schema_version":1}\n', encoding="utf-8")
    digest = report_bundle.calculate_sha256(report_path)
    checksum_path_for(report_path).write_text(f"{digest}  {report_path.name}\n", encoding="utf-8")
    updated = manifest.model_copy(
        update={
            "report": manifest.report.model_copy(update={"sha256": digest}),
            "checksum": manifest.checksum.model_copy(
                update={"sha256": report_bundle.calculate_sha256(checksum_path_for(report_path))}
            ),
        }
    )
    export_report_bundle_manifest(path=manifest_path_for(report_path), manifest=updated)

    with pytest.raises(AuditReportValidationError):
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)


def test_verify_report_bundle_uses_compare_digest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    calls: list[tuple[str, str]] = []
    original = report_bundle.hmac.compare_digest

    def wrapped(left: str, right: str) -> bool:
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(report_bundle.hmac, "compare_digest", wrapped)

    verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)

    assert len(calls) >= 3


def test_errors_do_not_expose_secret_manifest_or_digest(tmp_path: Path) -> None:
    report_path, _ = export_bundle(tmp_path)
    manifest_path_for(report_path).write_text(PRIVATE_TEXT, encoding="utf-8")

    with pytest.raises(ReportBundleManifestValidationError) as exc_info:
        verify_report_bundle(report_path=report_path, trust_store=trust_store(), verification_time=VERIFICATION_TIME)

    message = str(exc_info.value)
    assert PRIVATE_TEXT not in message
    assert SECRET.decode() not in message
    assert "0" * 64 not in message
