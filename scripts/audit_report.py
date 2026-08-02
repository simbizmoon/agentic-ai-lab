"""Print a local report from structured analysis audit logs."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audit_report import (
    AuditReportFilter,
    AuditReportFormat,
    AuditStatusFilter,
    build_audit_report,
    filter_audit_events,
    read_audit_events,
    render_audit_report,
)
from app.exceptions import AuditLogError, ReportExportError
from app.recovery import decide_recovery
from app.report_export import export_json_report

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "structured_analysis.jsonl"


def parse_cli_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "datetime must be ISO 8601 with timezone"
        ) from error
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
    parser.add_argument(
        "--output",
        type=Path,
        help="Atomically export a JSON audit report to this file path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.output is not None and args.format != AuditReportFormat.JSON.value:
        parser.error("--output requires --format json")

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
        filtered_events = filter_audit_events(
            events=events,
            report_filter=report_filter,
        )
        report = build_audit_report(filtered_events)
        rendered_report = render_audit_report(
            report=report,
            report_filter=report_filter,
            report_format=AuditReportFormat(args.format),
        )
        if args.output is not None:
            export_json_report(path=args.output, json_text=rendered_report)
            print("Audit report exported successfully.")
            print(f"Output: {args.output}")
            return 0

        print(rendered_report)
        return 0
    except (AuditLogError, ReportExportError) as error:
        decision = decide_recovery(error)
        print("[ERROR] Audit report generation failed")
        print(f"Action: {decision.action.value}")
        print(f"Retryable: {str(decision.retryable).lower()}")
        print(f"Reason: {decision.reason}")
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
