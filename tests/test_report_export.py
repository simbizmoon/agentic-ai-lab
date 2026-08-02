from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app import report_export
from app.audit_report import validate_audit_report_json
from app.exceptions import (
    AuditReportValidationError,
    InvalidReportExportPathError,
    ReportExportWriteError,
)
from app.report_export import _validate_export_path, export_json_report

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
PRIVATE_PATH = "PRIVATE-PATH"
PRIVATE_JSON = "PRIVATE-JSON"
PRIVATE_REPLACE_ERROR = "PRIVATE-REPLACE-ERROR"


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
