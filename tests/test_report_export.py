from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app import report_export
from app.audit_report import validate_audit_report_json
from app.authentication_trust import (
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    AuditReportValidationError,
    AuthenticationExportError,
    ChecksumExportError,
    InvalidReportExportPathError,
    MultipleActiveAuthenticationKeysError,
    NoActiveAuthenticationKeyError,
    ReportArchiveExportError,
    ReportBundleExportError,
    ReportExportWriteError,
)
from app.report_archive import (
    ReportArchiveExportResult,
    archive_path_for,
    verify_report_archive,
)
from app.report_authenticity import (
    ReportAuthentication,
    authentication_path_for,
    verify_report_authenticity,
)
from app.report_bundle import (
    AuditReportBundleManifest,
    manifest_path_for,
    verify_report_bundle,
)
from app.report_export import (
    _validate_export_path,
    export_json_report,
    export_json_report_archive,
    export_json_report_bundle,
    export_json_report_with_authentication,
    export_json_report_with_checksum,
)
from app.report_integrity import (
    ReportChecksum,
    checksum_path_for,
    verify_report_integrity,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
PRIVATE_PATH = "PRIVATE-PATH"
PRIVATE_JSON = "PRIVATE-JSON"
PRIVATE_REPLACE_ERROR = "PRIVATE-REPLACE-ERROR"
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)


def valid_json_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def invalid_contract_json() -> str:
    payload = json.loads(valid_json_text())
    payload["schema_version"] = 999
    return json.dumps(payload)


def test_validate_export_path_accepts_json_extension(tmp_path: Path) -> None:
    _validate_export_path(tmp_path / "report.json")


def test_validate_export_path_accepts_uppercase_json_extension(tmp_path: Path) -> None:
    _validate_export_path(tmp_path / "report.JSON")


@pytest.mark.parametrize("name", ["report", "report.txt", "report.jsonl"])
def test_validate_export_path_rejects_invalid_extensions(
    tmp_path: Path,
    name: str,
) -> None:
    with pytest.raises(InvalidReportExportPathError):
        _validate_export_path(tmp_path / name)


def test_validate_export_path_rejects_existing_directory(tmp_path: Path) -> None:
    directory = tmp_path / "report.json"
    directory.mkdir()

    with pytest.raises(InvalidReportExportPathError):
        _validate_export_path(directory)


def test_validate_export_path_rejects_existing_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink is unavailable: {error}")

    with pytest.raises(InvalidReportExportPathError):
        _validate_export_path(link)


def test_export_json_report_rejects_non_path() -> None:
    with pytest.raises(TypeError):
        export_json_report(path="report.json", json_text=valid_json_text())  # type: ignore[arg-type]


def test_invalid_path_error_omits_private_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidReportExportPathError) as exc_info:
        export_json_report(path=tmp_path / f"{PRIVATE_PATH}.txt", json_text=valid_json_text())

    assert PRIVATE_PATH not in str(exc_info.value)


def test_export_json_report_accepts_valid_json(tmp_path: Path) -> None:
    export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())


def test_export_json_report_rejects_malformed_json(tmp_path: Path) -> None:
    with pytest.raises(AuditReportValidationError):
        export_json_report(path=tmp_path / "report.json", json_text=f"{{{PRIVATE_JSON}")


def test_export_json_report_rejects_contract_mismatch(tmp_path: Path) -> None:
    with pytest.raises(AuditReportValidationError):
        export_json_report(path=tmp_path / "report.json", json_text=invalid_contract_json())


def test_validation_failure_does_not_create_parent_directory(tmp_path: Path) -> None:
    parent = tmp_path / "missing"

    with pytest.raises(AuditReportValidationError):
        export_json_report(path=parent / "report.json", json_text=invalid_contract_json())

    assert not parent.exists()


def test_validation_failure_does_not_create_target_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    with pytest.raises(AuditReportValidationError):
        export_json_report(path=target, json_text=invalid_contract_json())

    assert not target.exists()


def test_validation_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(AuditReportValidationError):
        export_json_report(path=target, json_text=invalid_contract_json())

    assert target.read_text(encoding="utf-8") == "existing"


def test_validation_error_omits_private_json(tmp_path: Path) -> None:
    with pytest.raises(AuditReportValidationError) as exc_info:
        export_json_report(path=tmp_path / "report.json", json_text=f"{{{PRIVATE_JSON}")

    assert PRIVATE_JSON not in str(exc_info.value)


def test_export_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert target.parent.is_dir()


def test_export_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert target.is_file()


def test_export_writes_utf8_json(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert target.read_text(encoding="utf-8").startswith("{")


def test_export_output_is_json_loadable(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    json.loads(target.read_text(encoding="utf-8"))


def test_export_output_passes_contract_validation(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    validate_audit_report_json(target.read_text(encoding="utf-8"))


def test_export_writes_exactly_one_trailing_newline(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text() + "\n\n")

    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_export_calls_fsync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[int] = []
    original_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(report_export.os, "fsync", recording_fsync)

    export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())

    assert len(calls) == 1


def test_export_calls_os_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        calls.append((source, destination))
        original_replace(source, destination)

    monkeypatch.setattr(report_export.os, "replace", recording_replace)
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert len(calls) == 1
    assert calls[0][1] == target


def test_export_replaces_existing_target_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    target.write_text("existing", encoding="utf-8")

    export_json_report(path=target, json_text=valid_json_text())

    assert target.read_text(encoding="utf-8") != "existing"


def test_export_leaves_no_temporary_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_export_does_not_mutate_input_json_text(tmp_path: Path) -> None:
    text = valid_json_text()
    before = text[:]

    export_json_report(path=tmp_path / "report.json", json_text=text)

    assert text == before


def test_export_converts_mkdir_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_mkdir(self: Path, *args: Any, **kwargs: Any) -> None:
        raise OSError("PRIVATE-MKDIR-ERROR")

    monkeypatch.setattr(Path, "mkdir", broken_mkdir)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=tmp_path / "nested" / "report.json", json_text=valid_json_text())


def test_export_converts_named_temporary_file_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_temp_file(*args: Any, **kwargs: Any) -> Any:
        raise OSError("PRIVATE-TEMP-ERROR")

    monkeypatch.setattr(report_export, "NamedTemporaryFile", broken_temp_file)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())


def test_export_converts_fsync_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_fsync(fd: int) -> None:
        raise OSError("PRIVATE-FSYNC-ERROR")

    monkeypatch.setattr(report_export.os, "fsync", broken_fsync)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())


def test_export_converts_replace_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_REPLACE_ERROR)

    monkeypatch.setattr(report_export.os, "replace", broken_replace)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())


def test_replace_failure_preserves_existing_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"
    target.write_text("existing", encoding="utf-8")

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_REPLACE_ERROR)

    monkeypatch.setattr(report_export.os, "replace", broken_replace)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=target, json_text=valid_json_text())

    assert target.read_text(encoding="utf-8") == "existing"


def test_replace_failure_cleans_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_REPLACE_ERROR)

    monkeypatch.setattr(report_export.os, "replace", broken_replace)

    with pytest.raises(ReportExportWriteError):
        export_json_report(path=target, json_text=valid_json_text())

    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_replace_error_message_omits_private_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_REPLACE_ERROR)

    monkeypatch.setattr(report_export.os, "replace", broken_replace)

    with pytest.raises(ReportExportWriteError) as exc_info:
        export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())

    assert PRIVATE_REPLACE_ERROR not in str(exc_info.value)
    assert "report.json" not in str(exc_info.value)


def test_unlink_failure_does_not_replace_original_export_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_REPLACE_ERROR)

    def broken_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        raise OSError("PRIVATE-UNLINK-ERROR")

    monkeypatch.setattr(report_export.os, "replace", broken_replace)
    monkeypatch.setattr(Path, "unlink", broken_unlink)

    with pytest.raises(ReportExportWriteError) as exc_info:
        export_json_report(path=tmp_path / "report.json", json_text=valid_json_text())

    assert PRIVATE_REPLACE_ERROR not in str(exc_info.value)
    assert "PRIVATE-UNLINK-ERROR" not in str(exc_info.value)


def test_export_json_report_with_checksum_succeeds(tmp_path: Path) -> None:
    checksum = export_json_report_with_checksum(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
    )

    assert isinstance(checksum, ReportChecksum)


def test_export_json_report_with_checksum_creates_json_file(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_checksum(path=target, json_text=valid_json_text())

    assert target.is_file()


def test_export_json_report_with_checksum_creates_sidecar(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_checksum(path=target, json_text=valid_json_text())

    assert checksum_path_for(target).is_file()


def test_export_json_report_with_checksum_returns_checksum(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    checksum = export_json_report_with_checksum(path=target, json_text=valid_json_text())

    assert checksum.filename == target.name
    assert checksum.digest


def test_export_json_report_with_checksum_matches_json(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_checksum(path=target, json_text=valid_json_text())

    verify_report_integrity(report_path=target)


def test_export_json_report_with_checksum_hashes_final_newline(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    checksum = export_json_report_with_checksum(path=target, json_text=valid_json_text().rstrip("\n"))

    assert target.read_text(encoding="utf-8").endswith("\n")
    assert verify_report_integrity(report_path=target).digest == checksum.digest


def test_checksum_failure_keeps_json_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"

    def fail_checksum(**kwargs: object) -> None:
        raise ChecksumExportError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(report_export, "export_checksum_file", fail_checksum)

    with pytest.raises(ChecksumExportError):
        export_json_report_with_checksum(path=target, json_text=valid_json_text())

    assert target.is_file()


def test_checksum_failure_propagates_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_checksum(**kwargs: object) -> None:
        raise ChecksumExportError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(report_export, "export_checksum_file", fail_checksum)

    with pytest.raises(ChecksumExportError):
        export_json_report_with_checksum(path=tmp_path / "report.json", json_text=valid_json_text())


def test_existing_export_json_report_still_writes_json_only(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report(path=target, json_text=valid_json_text())

    assert target.is_file()
    assert not checksum_path_for(target).exists()


def test_export_with_checksum_runs_json_before_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def record_json_export(**kwargs: object) -> None:
        calls.append("json")
        Path(kwargs["path"]).write_text(valid_json_text(), encoding="utf-8")

    def record_build_checksum(path: Path) -> ReportChecksum:
        calls.append("build")
        return ReportChecksum("sha256", "a" * 64, path.name)

    def record_checksum_path(path: Path) -> Path:
        calls.append("path")
        return path.parent / f"{path.name}.sha256"

    def record_checksum_export(**kwargs: object) -> None:
        calls.append("checksum")

    monkeypatch.setattr(report_export, "export_json_report", record_json_export)
    monkeypatch.setattr(report_export, "build_report_checksum", record_build_checksum)
    monkeypatch.setattr(report_export, "checksum_path_for", record_checksum_path)
    monkeypatch.setattr(report_export, "export_checksum_file", record_checksum_export)

    export_json_report_with_checksum(path=tmp_path / "report.json", json_text=valid_json_text())

    assert calls == ["json", "build", "path", "checksum"]



def trusted_key(
    key_id: str = "key-1",
    secret: bytes = b"s" * 32,
    *,
    status: AuthenticationKeyStatus = AuthenticationKeyStatus.ACTIVE,
) -> TrustedAuthenticationKey:
    return TrustedAuthenticationKey(
        key_id=key_id,
        secret=secret,
        status=status,
        valid_from=datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
        revoked_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        if status is AuthenticationKeyStatus.REVOKED
        else None,
    )


def trust_store(*keys: TrustedAuthenticationKey) -> AuthenticationTrustStore:
    return AuthenticationTrustStore(keys=keys or (trusted_key(),))


def test_export_json_report_with_authentication_succeeds(tmp_path: Path) -> None:
    checksum, authentication = export_json_report_with_authentication(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert checksum.digest
    assert isinstance(authentication, ReportAuthentication)
    assert authentication.algorithm == "hmac-sha256-v2"
    assert authentication.authenticated_at == AUTHENTICATED_AT


def test_export_json_report_with_authentication_creates_json(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert target.is_file()


def test_export_json_report_with_authentication_creates_checksum(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert checksum_path_for(target).is_file()


def test_export_json_report_with_authentication_creates_hmac(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert authentication_path_for(target).is_file()


def test_export_json_report_with_authentication_returns_tuple(tmp_path: Path) -> None:
    result = export_json_report_with_authentication(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert len(result) == 2


def test_export_json_report_with_authentication_checksum_verifies(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    verify_report_integrity(report_path=target)


def test_export_json_report_with_authentication_hmac_verifies(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    verify_report_authenticity(
        report_path=target,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )


def test_export_json_report_with_authentication_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def record_select_signing_key(**kwargs: object) -> TrustedAuthenticationKey:
        calls.append("select")
        return trusted_key()

    def record_checksum(**kwargs: object) -> object:
        calls.append("checksum")
        Path(kwargs["path"]).write_text(valid_json_text(), encoding="utf-8")
        checksum_path_for(Path(kwargs["path"])).write_text(
            f"{'a' * 64}  report.json\n",
            encoding="utf-8",
        )
        return object()

    def record_build_auth(**kwargs: object) -> ReportAuthentication:
        calls.append("build-auth")
        return ReportAuthentication(
            "hmac-sha256-v2",
            2,
            "key-1",
            AUTHENTICATED_AT,
            "b" * 64,
            "report.json",
        )

    def record_auth_path(path: Path) -> Path:
        calls.append("auth-path")
        return path.parent / f"{path.name}.hmac"

    def record_auth_export(**kwargs: object) -> None:
        calls.append("auth-export")

    monkeypatch.setattr(report_export, "select_signing_key", record_select_signing_key)
    monkeypatch.setattr(report_export, "export_json_report_with_checksum", record_checksum)
    monkeypatch.setattr(report_export, "build_report_authentication", record_build_auth)
    monkeypatch.setattr(report_export, "authentication_path_for", record_auth_path)
    monkeypatch.setattr(report_export, "export_authentication_file", record_auth_export)

    export_json_report_with_authentication(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert calls == ["select", "checksum", "build-auth", "auth-path", "auth-export"]


def test_hmac_failure_keeps_json_and_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"

    def fail_auth_export(**kwargs: object) -> None:
        raise AuthenticationExportError("PRIVATE-HMAC-SECRET")

    monkeypatch.setattr(report_export, "export_authentication_file", fail_auth_export)

    with pytest.raises(AuthenticationExportError):
        export_json_report_with_authentication(
            path=target,
            json_text=valid_json_text(),
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
        )

    assert target.exists()
    assert checksum_path_for(target).exists()


def test_hmac_failure_propagates_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_auth_export(**kwargs: object) -> None:
        raise AuthenticationExportError("PRIVATE-HMAC-SECRET")

    monkeypatch.setattr(report_export, "export_authentication_file", fail_auth_export)

    with pytest.raises(AuthenticationExportError):
        export_json_report_with_authentication(
            path=tmp_path / "report.json",
            json_text=valid_json_text(),
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
        )


def test_authentication_export_does_not_store_secret(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert "ssss" not in authentication_path_for(target).read_text(encoding="utf-8")


def test_export_with_authentication_uses_active_key(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    store = trust_store(
        trusted_key("old-key", b"o" * 32, status=AuthenticationKeyStatus.VERIFY_ONLY),
        trusted_key("new-key", b"n" * 32),
    )

    _, authentication = export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=store,
        authenticated_at=AUTHENTICATED_AT,
    )

    assert authentication.key_id == "new-key"


def test_export_with_authentication_does_not_use_verify_only_key(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    store = trust_store(
        trusted_key("old-key", b"o" * 32, status=AuthenticationKeyStatus.VERIFY_ONLY),
        trusted_key("new-key", b"n" * 32),
    )

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=store,
        authenticated_at=AUTHENTICATED_AT,
    )

    sidecar = authentication_path_for(target).read_text(encoding="utf-8")
    assert "  new-key  " in sidecar
    assert "  old-key  " not in sidecar


def test_export_with_authentication_key_order_does_not_change_active_key(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    keys_a = (
        trusted_key("old-key", b"o" * 32, status=AuthenticationKeyStatus.VERIFY_ONLY),
        trusted_key("new-key", b"n" * 32),
    )
    keys_b = tuple(reversed(keys_a))

    _, auth_a = export_json_report_with_authentication(
        path=first,
        json_text=valid_json_text(),
        trust_store=trust_store(*keys_a),
        authenticated_at=AUTHENTICATED_AT,
    )
    _, auth_b = export_json_report_with_authentication(
        path=second,
        json_text=valid_json_text(),
        trust_store=trust_store(*keys_b),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert auth_a.key_id == auth_b.key_id == "new-key"


def test_export_with_authentication_active_key_rotation_changes_new_sidecar_key_id(tmp_path: Path) -> None:
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"

    _, old_auth = export_json_report_with_authentication(
        path=old_path,
        json_text=valid_json_text(),
        trust_store=trust_store(trusted_key("old-key", b"o" * 32)),
        authenticated_at=AUTHENTICATED_AT,
    )
    _, new_auth = export_json_report_with_authentication(
        path=new_path,
        json_text=valid_json_text(),
        trust_store=trust_store(trusted_key("new-key", b"n" * 32)),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert old_auth.key_id == "old-key"
    assert new_auth.key_id == "new-key"


def test_export_with_authentication_rejects_verify_only_only_store(tmp_path: Path) -> None:
    with pytest.raises(NoActiveAuthenticationKeyError):
        export_json_report_with_authentication(
            path=tmp_path / "report.json",
            json_text=valid_json_text(),
            trust_store=trust_store(
                trusted_key("old-key", b"o" * 32, status=AuthenticationKeyStatus.VERIFY_ONLY)
            ),
            authenticated_at=AUTHENTICATED_AT,
        )


def test_export_with_authentication_rejects_revoked_only_store(tmp_path: Path) -> None:
    with pytest.raises(NoActiveAuthenticationKeyError):
        export_json_report_with_authentication(
            path=tmp_path / "report.json",
            json_text=valid_json_text(),
            trust_store=trust_store(
                trusted_key("old-key", b"o" * 32, status=AuthenticationKeyStatus.REVOKED)
            ),
            authenticated_at=AUTHENTICATED_AT,
        )


def test_export_with_authentication_rejects_multiple_active_keys(tmp_path: Path) -> None:
    with pytest.raises(MultipleActiveAuthenticationKeysError):
        export_json_report_with_authentication(
            path=tmp_path / "report.json",
            json_text=valid_json_text(),
            trust_store=trust_store(
                trusted_key("old-key", b"o" * 32),
                trusted_key("new-key", b"n" * 32),
            ),
            authenticated_at=AUTHENTICATED_AT,
        )



def test_export_json_report_bundle_succeeds(tmp_path: Path) -> None:
    checksum, authentication, manifest = export_json_report_bundle(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert checksum.digest
    assert authentication.digest
    assert isinstance(manifest, AuditReportBundleManifest)


def test_export_json_report_bundle_creates_four_files(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_bundle(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert target.is_file()
    assert checksum_path_for(target).is_file()
    assert authentication_path_for(target).is_file()
    assert manifest_path_for(target).is_file()


def test_export_json_report_bundle_verifies(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_bundle(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    verify_report_bundle(
        report_path=target,
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    )


def test_export_json_report_bundle_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def record_auth(**kwargs: object) -> tuple[ReportChecksum, ReportAuthentication]:
        calls.append("auth")
        path = Path(kwargs["path"])
        path.write_text(valid_json_text(), encoding="utf-8")
        checksum_path_for(path).write_text(f"{'a' * 64}  {path.name}\n", encoding="utf-8")
        authentication_path_for(path).write_text("auth", encoding="utf-8")
        return (
            ReportChecksum("sha256", "a" * 64, path.name),
            ReportAuthentication("hmac-sha256-v2", 2, "key-1", AUTHENTICATED_AT, "b" * 64, path.name),
        )

    def record_build_manifest(**kwargs: object) -> AuditReportBundleManifest:
        calls.append("manifest-build")
        return AuditReportBundleManifest(
            manifest_version=1,
            bundle_type="structured_analysis_audit_report_bundle",
            report={"filename": "report.json", "schema_version": 1, "sha256": "a" * 64},
            checksum={"filename": "report.json.sha256", "sha256": "b" * 64},
            authentication={
                "filename": "report.json.hmac",
                "sha256": "c" * 64,
                "algorithm": "hmac-sha256-v2",
                "protocol_version": 2,
                "key_id": "key-1",
                "authenticated_at": AUTHENTICATED_AT,
            },
        )

    def record_manifest_path(path: Path) -> Path:
        calls.append("manifest-path")
        return path.parent / f"{path.name}.manifest"

    def record_manifest_export(**kwargs: object) -> None:
        calls.append("manifest-export")

    monkeypatch.setattr(report_export, "export_json_report_with_authentication", record_auth)
    monkeypatch.setattr(report_export, "build_report_bundle_manifest", record_build_manifest)
    monkeypatch.setattr(report_export, "manifest_path_for", record_manifest_path)
    monkeypatch.setattr(report_export, "export_report_bundle_manifest", record_manifest_export)

    export_json_report_bundle(
        path=tmp_path / "report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert calls == ["auth", "manifest-build", "manifest-path", "manifest-export"]


def test_manifest_failure_keeps_json_checksum_and_hmac(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"

    def fail_manifest_export(**kwargs: object) -> None:
        raise ReportBundleExportError("PRIVATE-BUNDLE-ERROR")

    monkeypatch.setattr(report_export, "export_report_bundle_manifest", fail_manifest_export)

    with pytest.raises(ReportBundleExportError):
        export_json_report_bundle(
            path=target,
            json_text=valid_json_text(),
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
        )

    assert target.exists()
    assert checksum_path_for(target).exists()
    assert authentication_path_for(target).exists()


def test_existing_non_authenticated_export_still_skips_manifest(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_checksum(path=target, json_text=valid_json_text())

    assert not authentication_path_for(target).exists()
    assert not manifest_path_for(target).exists()


def test_existing_authenticated_export_still_skips_manifest(tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    export_json_report_with_authentication(
        path=target,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert authentication_path_for(target).exists()
    assert not manifest_path_for(target).exists()

def test_export_json_report_archive_succeeds(tmp_path: Path) -> None:
    result = export_json_report_archive(
        path=tmp_path / "audit-report.json",
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert isinstance(result[3], ReportArchiveExportResult)


def test_export_json_report_archive_creates_bundle_and_zip(tmp_path: Path) -> None:
    path = tmp_path / "audit-report.json"

    export_json_report_archive(
        path=path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert path.exists()
    assert checksum_path_for(path).exists()
    assert authentication_path_for(path).exists()
    assert manifest_path_for(path).exists()
    assert archive_path_for(path).exists()


def test_export_json_report_archive_verifies(tmp_path: Path) -> None:
    path = tmp_path / "audit-report.json"

    export_json_report_archive(
        path=path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert verify_report_archive(
        archive_path=archive_path_for(path),
        trust_store=trust_store(),
        verification_time=VERIFICATION_TIME,
    ).member_count == 4


def test_export_json_report_archive_failure_keeps_bundle_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit-report.json"

    def fail_archive(**kwargs: object) -> None:
        raise ReportArchiveExportError("PRIVATE-ARCHIVE-ERROR")

    monkeypatch.setattr(report_export, "export_report_archive", fail_archive)

    with pytest.raises(ReportArchiveExportError):
        export_json_report_archive(
            path=path,
            json_text=valid_json_text(),
            trust_store=trust_store(),
            authenticated_at=AUTHENTICATED_AT,
        )

    assert path.exists()
    assert checksum_path_for(path).exists()
    assert authentication_path_for(path).exists()
    assert manifest_path_for(path).exists()
    assert not archive_path_for(path).exists()


def test_existing_bundle_export_still_skips_archive(tmp_path: Path) -> None:
    path = tmp_path / "audit-report.json"

    export_json_report_bundle(
        path=path,
        json_text=valid_json_text(),
        trust_store=trust_store(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert not archive_path_for(path).exists()
