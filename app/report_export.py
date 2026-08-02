"""Safely export validated audit report JSON to a file."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.audit_report import validate_audit_report_json
from app.exceptions import InvalidReportExportPathError, ReportExportWriteError
from app.report_integrity import (
    ReportChecksum,
    build_report_checksum,
    checksum_path_for,
    export_checksum_file,
)


def _validate_export_path(path: Path) -> None:
    if not path.name:
        raise InvalidReportExportPathError("The audit report export path is invalid.")
    if path.suffix.lower() != ".json":
        raise InvalidReportExportPathError("The audit report export path is invalid.")
    if path.is_dir():
        raise InvalidReportExportPathError("The audit report export path is invalid.")
    if path.is_symlink():
        raise InvalidReportExportPathError("The audit report export path is invalid.")


def export_json_report(
    *,
    path: Path,
    json_text: str,
) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")

    _validate_export_path(path)
    validate_audit_report_json(json_text)

    normalized_json = json_text.rstrip("\n") + "\n"
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
            temp_file.write(normalized_json)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)
        replaced = True
    except OSError as error:
        raise ReportExportWriteError("Failed to export the audit report.") from error
    finally:
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def export_json_report_with_checksum(
    *,
    path: Path,
    json_text: str,
) -> ReportChecksum:
    export_json_report(path=path, json_text=json_text)
    checksum = build_report_checksum(path)
    export_checksum_file(
        checksum_path=checksum_path_for(path),
        checksum=checksum,
    )
    return checksum
