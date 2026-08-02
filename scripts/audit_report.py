"""Print a local report from structured analysis audit logs."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.archive_authenticity import (
    REPORT_ARCHIVE_FORMAT_VERSION,
    archive_authentication_path_for,
    verify_archive_authenticity,
)
from app.archive_signature import (
    archive_signature_path_for,
    verify_archive_signature,
)
from app.audit_report import (
    AuditReportFilter,
    AuditReportFormat,
    AuditStatusFilter,
    build_audit_report,
    filter_audit_events,
    read_audit_events,
    render_audit_report,
)
from app.authentication_trust import (
    RevokedKeyPolicy,
    load_authentication_trust_store,
)
from app.exceptions import (
    ArchiveAuthenticityError,
    ArchiveSignatureError,
    AuditLogError,
    ReportArchiveError,
    ReportAuthenticityError,
    ReportBundleError,
    ReportExportError,
    ReportIntegrityError,
)
from app.recovery import decide_recovery
from app.report_archive import (
    archive_path_for,
    verify_authenticated_report_archive,
    verify_signed_authenticated_report_archive,
)
from app.report_authenticity import (
    authentication_path_for,
    verify_report_authenticity,
)
from app.report_bundle import manifest_path_for, verify_report_bundle
from app.report_export import (
    export_json_report_archive,
    export_json_report_bundle,
    export_json_report_signed_archive,
    export_json_report_with_checksum,
)
from app.report_integrity import (
    checksum_path_for,
    verify_report_integrity,
)
from app.signature_trust import (
    RevokedSignatureKeyPolicy,
    load_archive_signature_trust_store,
    load_archive_signing_private_key,
)

_MONKEYPATCH_COMPATIBILITY_EXPORTS = (
    export_json_report_archive,
    verify_authenticated_report_archive,
)

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "structured_analysis.jsonl"


def parse_cli_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("datetime must be ISO 8601 with timezone") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must include timezone")
    return parsed.astimezone(UTC)


def parse_model_filter(value: str) -> str:
    model = value.strip()
    if not model:
        raise argparse.ArgumentTypeError("model must not be empty")
    return model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a local structured analysis audit report."
    )
    parser.add_argument("--since", type=parse_cli_datetime)
    parser.add_argument("--until", type=parse_cli_datetime)
    parser.add_argument("--model", type=parse_model_filter)
    parser.add_argument(
        "--status",
        choices=[status.value for status in AuditStatusFilter],
        default=AuditStatusFilter.ALL.value,
    )
    parser.add_argument(
        "--format",
        choices=[report_format.value for report_format in AuditReportFormat],
        default=AuditReportFormat.TEXT.value,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--authenticate", action="store_true")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--verify-authenticity", type=Path)
    parser.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--verify-archive", type=Path)
    parser.add_argument("--verify-archive-authenticity", type=Path)
    parser.add_argument("--verify-archive-signature", type=Path)
    parser.add_argument(
        "--revoked-key-policy",
        choices=[policy.value for policy in RevokedKeyPolicy],
        default=RevokedKeyPolicy.REJECT.value,
    )
    parser.add_argument(
        "--revoked-signature-key-policy",
        choices=[policy.value for policy in RevokedSignatureKeyPolicy],
        default=RevokedSignatureKeyPolicy.REJECT.value,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_mode_args(parser, args)

    if args.verify is not None:
        return _run_verify(args.verify)
    if args.verify_authenticity is not None:
        return _run_verify_authenticity(
            args.verify_authenticity,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_bundle is not None:
        return _run_verify_bundle(
            args.verify_bundle,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_archive_authenticity is not None:
        return _run_verify_archive_authenticity(
            args.verify_archive_authenticity,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_archive_signature is not None:
        return _run_verify_archive_signature(
            args.verify_archive_signature,
            revoked_signature_key_policy=RevokedSignatureKeyPolicy(
                args.revoked_signature_key_policy
            ),
        )
    if args.verify_archive is not None:
        return _run_verify_archive(
            args.verify_archive,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
            revoked_signature_key_policy=RevokedSignatureKeyPolicy(
                args.revoked_signature_key_policy
            ),
        )

    return _run_report_generation(args, parser)


def _validate_mode_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    verify_modes = (
        args.verify,
        args.verify_authenticity,
        args.verify_bundle,
        args.verify_archive_authenticity,
        args.verify_archive_signature,
        args.verify_archive,
    )
    if sum(value is not None for value in verify_modes) > 1:
        parser.error("only one verify mode can be used at a time")

    hmac_policy_used = args.revoked_key_policy != RevokedKeyPolicy.REJECT.value
    signature_policy_used = (
        args.revoked_signature_key_policy != RevokedSignatureKeyPolicy.REJECT.value
    )
    if args.verify is not None:
        _validate_common_verify_args(parser, args, "--verify")
        if hmac_policy_used:
            parser.error("--verify cannot be used with --revoked-key-policy")
        if signature_policy_used:
            parser.error("--verify cannot be used with --revoked-signature-key-policy")
    elif args.verify_authenticity is not None:
        _validate_common_verify_args(parser, args, "--verify-authenticity")
        if signature_policy_used:
            parser.error(
                "--verify-authenticity cannot be used with --revoked-signature-key-policy"
            )
    elif args.verify_bundle is not None:
        _validate_common_verify_args(parser, args, "--verify-bundle")
        if signature_policy_used:
            parser.error("--verify-bundle cannot be used with --revoked-signature-key-policy")
    elif args.verify_archive_authenticity is not None:
        _validate_common_verify_args(parser, args, "--verify-archive-authenticity")
        if signature_policy_used:
            parser.error(
                "--verify-archive-authenticity cannot be used with --revoked-signature-key-policy"
            )
    elif args.verify_archive_signature is not None:
        _validate_common_verify_args(parser, args, "--verify-archive-signature")
        if hmac_policy_used:
            parser.error("--verify-archive-signature cannot be used with --revoked-key-policy")
    elif args.verify_archive is not None:
        _validate_common_verify_args(parser, args, "--verify-archive")
    elif hmac_policy_used:
        parser.error("--revoked-key-policy can only be used with verify modes")
    elif signature_policy_used:
        parser.error("--revoked-signature-key-policy can only be used with signature verify modes")

    if args.archive and args.output is None:
        parser.error("--archive requires --output")
    if args.archive and not args.authenticate:
        parser.error("--archive requires --authenticate")
    if args.authenticate and args.output is None:
        parser.error("--authenticate requires --output")
    if args.output is not None and args.format != AuditReportFormat.JSON.value:
        parser.error("--output requires --format json")


def _validate_common_verify_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    option_name: str,
) -> None:
    if args.output is not None:
        parser.error(f"{option_name} cannot be used with --output")
    if args.authenticate:
        parser.error(f"{option_name} cannot be used with --authenticate")
    if args.archive:
        parser.error(f"{option_name} cannot be used with --archive")
    if args.since is not None:
        parser.error(f"{option_name} cannot be used with --since")
    if args.until is not None:
        parser.error(f"{option_name} cannot be used with --until")
    if args.model is not None:
        parser.error(f"{option_name} cannot be used with --model")
    if args.status != AuditStatusFilter.ALL.value:
        parser.error(f"{option_name} cannot be used with --status")
    if args.format == AuditReportFormat.JSON.value:
        parser.error(f"{option_name} cannot be used with --format json")


def _run_report_generation(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        report_filter = AuditReportFilter(
            since=args.since,
            until=args.until,
            model=args.model,
            status=AuditStatusFilter(args.status),
        )
    except ValueError as error:
        parser.error(str(error))

    try:
        events = read_audit_events(AUDIT_LOG_PATH)
        filtered_events = filter_audit_events(events=events, report_filter=report_filter)
        report = build_audit_report(filtered_events)
        rendered_report = render_audit_report(
            report=report,
            report_filter=report_filter,
            report_format=AuditReportFormat(args.format),
        )
        if args.output is None:
            print(rendered_report)
            return 0
        if args.authenticate:
            return _export_authenticated_report(args, rendered_report)
        checksum = export_json_report_with_checksum(path=args.output, json_text=rendered_report)
        print("Audit report exported successfully.")
        print(f"Output: {args.output}")
        print(f"Checksum: {checksum_path_for(args.output)}")
        print(f"SHA-256: {checksum.digest}")
        return 0
    except (
        ArchiveAuthenticityError,
        ArchiveSignatureError,
        AuditLogError,
        ReportArchiveError,
        ReportAuthenticityError,
        ReportBundleError,
        ReportExportError,
        ReportIntegrityError,
    ) as error:
        _print_recovery_error(header="[ERROR] Audit report generation failed", error=error)
        return 5


def _export_authenticated_report(args: argparse.Namespace, rendered_report: str) -> int:
    exported_at = datetime.now(UTC)
    trust_store = load_authentication_trust_store(environ=os.environ)
    if args.archive:
        signing_key = load_archive_signing_private_key(environ=os.environ)
        signature_trust_store = load_archive_signature_trust_store(environ=os.environ)
        checksum, authentication, manifest, archive, archive_authentication, signature = (
            export_json_report_signed_archive(
                path=args.output,
                json_text=rendered_report,
                trust_store=trust_store,
                authenticated_at=exported_at,
                signing_key=signing_key,
                signature_trust_store=signature_trust_store,
                signed_at=exported_at,
            )
        )
    else:
        checksum, authentication, manifest = export_json_report_bundle(
            path=args.output,
            json_text=rendered_report,
            trust_store=trust_store,
            authenticated_at=exported_at,
        )
        archive = None
        archive_authentication = None
        signature = None

    print("Audit report exported successfully.")
    print(f"Output: {args.output}")
    print(f"Checksum: {checksum_path_for(args.output)}")
    print(f"SHA-256: {checksum.digest}")
    print(f"Authentication: {authentication_path_for(args.output)}")
    print(f"Manifest: {manifest_path_for(args.output)}")
    print(f"Manifest Version: {manifest.manifest_version}")
    print(f"Algorithm: {authentication.algorithm}")
    print(f"Key ID: {authentication.key_id}")
    print(f"Authenticated At: {authentication.authenticated_at.isoformat()}")
    print(f"HMAC: {authentication.digest}")
    if archive is not None and archive_authentication is not None and signature is not None:
        archive_path = archive_path_for(args.output)
        print(f"Archive: {archive_path}")
        print(f"Archive Format Version: {REPORT_ARCHIVE_FORMAT_VERSION}")
        print(f"Archive Members: {archive.member_count}")
        print(f"Archive SHA-256: {archive.archive_sha256}")
        print(f"Archive Authentication: {archive_authentication_path_for(archive_path)}")
        print(f"Archive Authentication Algorithm: {archive_authentication.algorithm}")
        print(
            "Archive Authentication Protocol Version: "
            f"{archive_authentication.protocol_version}"
        )
        print(f"Archive Authentication Key ID: {archive_authentication.key_id}")
        print(f"Archive Authenticated At: {archive_authentication.authenticated_at.isoformat()}")
        print(f"Archive HMAC: {archive_authentication.digest}")
        print(f"Signature: {archive_signature_path_for(archive_path)}")
        print(f"Signature Algorithm: {signature.algorithm}")
        print(f"Signature Protocol Version: {signature.signature_version}")
        print(f"Signature Key ID: {signature.key_id}")
        print(f"Signature Public Key Fingerprint: {signature.public_key_fingerprint}")
        print(f"Signed At: {signature.signed_at.isoformat()}")
        print(f"Signature Archive SHA-256: {signature.archive_sha256}")
    return 0


def _run_verify(verify_path: Path) -> int:
    try:
        result = verify_report_integrity(report_path=verify_path)
    except (AuditLogError, ReportIntegrityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report integrity verification failed",
            error=error,
        )
        return 5
    print("Audit report integrity verified.")
    print(f"File: {verify_path}")
    print(f"Checksum: {checksum_path_for(verify_path)}")
    print(f"SHA-256: {result.digest}")
    return 0


def _run_verify_authenticity(verify_path: Path, *, revoked_key_policy: RevokedKeyPolicy) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_report_authenticity(
            report_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_key_policy,
        )
    except (AuditLogError, ReportAuthenticityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report authenticity verification failed",
            error=error,
        )
        return 5
    print("Audit report authenticity verified.")
    print(f"File: {verify_path}")
    print(f"Authentication: {authentication_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    print(f"HMAC: {result.digest}")
    return 0


def _run_verify_bundle(verify_path: Path, *, revoked_key_policy: RevokedKeyPolicy) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_report_bundle(
            report_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_key_policy,
        )
    except (AuditLogError, ReportAuthenticityError, ReportBundleError, ReportIntegrityError) as error:
        _print_recovery_error(header="[ERROR] Audit report bundle verification failed", error=error)
        return 5
    print("Audit report bundle verified.")
    print(f"File: {verify_path}")
    print(f"Manifest: {manifest_path_for(verify_path)}")
    print(f"Manifest Version: {result.manifest_version}")
    print(f"Report Schema Version: {result.report_schema_version}")
    print(f"Authentication Protocol Version: {result.authentication_protocol_version}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    return 0


def _run_verify_archive_authenticity(
    verify_path: Path,
    *,
    revoked_key_policy: RevokedKeyPolicy,
) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_archive_authenticity(
            archive_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
            revoked_key_policy=revoked_key_policy,
        )
    except (ArchiveAuthenticityError, ReportAuthenticityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report archive authenticity verification failed",
            error=error,
        )
        return 5
    print("Audit report archive authenticity verified.")
    print(f"Archive: {verify_path}")
    print(f"Authentication: {archive_authentication_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Protocol Version: {result.protocol_version}")
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    print(f"Archive HMAC: {result.digest}")
    return 0


def _run_verify_archive_signature(
    verify_path: Path,
    *,
    revoked_signature_key_policy: RevokedSignatureKeyPolicy,
) -> int:
    try:
        signature_trust_store = load_archive_signature_trust_store(environ=os.environ)
        result = verify_archive_signature(
            archive_path=verify_path,
            signature_trust_store=signature_trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_signature_key_policy,
        )
    except ArchiveSignatureError as error:
        _print_recovery_error(
            header="[ERROR] Audit report archive signature verification failed",
            error=error,
        )
        return 5
    print("Audit report archive signature verified.")
    print(f"Archive: {verify_path}")
    print(f"Signature: {archive_signature_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Protocol Version: {result.protocol_version}")
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Key ID: {result.key_id}")
    print(f"Public Key Fingerprint: {result.public_key_fingerprint}")
    print(f"Signed At: {result.signed_at.isoformat()}")
    print(f"Archive SHA-256: {result.archive_sha256}")
    return 0


def _run_verify_archive(
    verify_path: Path,
    *,
    revoked_key_policy: RevokedKeyPolicy,
    revoked_signature_key_policy: RevokedSignatureKeyPolicy,
) -> int:
    try:
        signature_trust_store = load_archive_signature_trust_store(environ=os.environ)
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_signed_authenticated_report_archive(
            archive_path=verify_path,
            trust_store=trust_store,
            signature_trust_store=signature_trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_key_policy,
            revoked_signature_key_policy=revoked_signature_key_policy,
        )
    except (
        ArchiveAuthenticityError,
        ArchiveSignatureError,
        AuditLogError,
        ReportArchiveError,
        ReportAuthenticityError,
        ReportBundleError,
        ReportIntegrityError,
    ) as error:
        _print_recovery_error(header="[ERROR] Audit report archive verification failed", error=error)
        return 5
    print("Audit report archive verified.")
    print(f"Archive: {verify_path}")
    print(f"Signature Algorithm: {result.signature_algorithm}")
    print(f"Signature Protocol Version: {result.signature_protocol_version}")
    print(f"Signature Key ID: {result.signature_key_id}")
    print(f"Signature Public Key Fingerprint: {result.signature_public_key_fingerprint}")
    print(f"Signed At: {result.signature_signed_at.isoformat()}")
    print(f"Signature Archive SHA-256: {result.signature_archive_sha256}")
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Archive SHA-256: {result.archive_sha256}")
    print(f"Members: {result.member_count}")
    print(f"Manifest Version: {result.manifest_version}")
    print(f"Report Schema Version: {result.report_schema_version}")
    print(f"Archive Authentication Protocol Version: {result.archive_authentication_protocol_version}")
    print(f"Archive Authentication Algorithm: {result.archive_algorithm}")
    print(f"Archive Authentication Key ID: {result.archive_key_id}")
    print(f"Archive Authenticated At: {result.archive_authenticated_at.isoformat()}")
    print(f"Archive HMAC: {result.archive_digest}")
    print(f"Authentication Protocol Version: {result.report_authentication_protocol_version}")
    print(f"Algorithm: {result.report_algorithm}")
    print(f"Key ID: {result.report_key_id}")
    print(f"Authenticated At: {result.report_authenticated_at.isoformat()}")
    print(f"Report Filename: {result.report_filename}")
    return 0


def _print_recovery_error(*, header: str, error: BaseException) -> None:
    decision = decide_recovery(error)
    print(header)
    print(f"Action: {decision.action.value}")
    print(f"Retryable: {str(decision.retryable).lower()}")
    print(f"Reason: {decision.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
