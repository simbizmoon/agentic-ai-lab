"""Safely export validated audit report JSON to a file."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.audit_report import validate_audit_report_json
from app.authentication_trust import AuthenticationTrustStore, select_signing_key
from app.exceptions import InvalidReportExportPathError, ReportExportWriteError
from app.report_archive import (
    ReportArchiveExportResult,
    archive_path_for,
    export_report_archive,
)
from app.report_authenticity import (
    ReportAuthentication,
    authentication_path_for,
    build_report_authentication,
    export_authentication_file,
)
from app.report_bundle import (
    AuditReportBundleManifest,
    build_report_bundle_manifest,
    export_report_bundle_manifest,
    manifest_path_for,
)
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


def export_json_report_with_authentication(
    *,
    path: Path,
    json_text: str,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
) -> tuple[ReportChecksum, ReportAuthentication]:
    signing_key = select_signing_key(
        trust_store=trust_store,
        authenticated_at=authenticated_at,
    )
    checksum = export_json_report_with_checksum(path=path, json_text=json_text)
    authentication = build_report_authentication(
        report_path=path,
        key=signing_key,
        authenticated_at=authenticated_at,
    )
    export_authentication_file(
        authentication_path=authentication_path_for(path),
        authentication=authentication,
    )
    return checksum, authentication


def export_json_report_bundle(
    *,
    path: Path,
    json_text: str,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
) -> tuple[ReportChecksum, ReportAuthentication, AuditReportBundleManifest]:
    checksum, authentication = export_json_report_with_authentication(
        path=path,
        json_text=json_text,
        trust_store=trust_store,
        authenticated_at=authenticated_at,
    )
    manifest = build_report_bundle_manifest(report_path=path)
    export_report_bundle_manifest(
        path=manifest_path_for(path),
        manifest=manifest,
    )
    return checksum, authentication, manifest

def export_json_report_archive(
    *,
    path: Path,
    json_text: str,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
    archive_path: Path | None = None,
) -> tuple[
    ReportChecksum,
    ReportAuthentication,
    AuditReportBundleManifest,
    ReportArchiveExportResult,
]:
    checksum, authentication, manifest = export_json_report_bundle(
        path=path,
        json_text=json_text,
        trust_store=trust_store,
        authenticated_at=authenticated_at,
    )
    effective_archive_path = archive_path_for(path) if archive_path is None else archive_path
    archive = export_report_archive(
        report_path=path,
        archive_path=effective_archive_path,
        trust_store=trust_store,
        verification_time=authenticated_at,
    )
    return checksum, authentication, manifest, archive
