"""Print a local report from structured analysis audit logs."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audit_report import build_audit_report, format_audit_report, read_audit_events
from app.exceptions import AuditLogError
from app.recovery import decide_recovery

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "structured_analysis.jsonl"


def main() -> int:
    try:
        events = read_audit_events(AUDIT_LOG_PATH)
        report = build_audit_report(events)
        print(format_audit_report(report))
        return 0
    except AuditLogError as error:
        decision = decide_recovery(error)
        print("[ERROR] Audit report generation failed")
        print(f"Action: {decision.action.value}")
        print(f"Retryable: {str(decision.retryable).lower()}")
        print(f"Reason: {decision.reason}")
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
