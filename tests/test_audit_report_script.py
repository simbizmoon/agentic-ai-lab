from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import scripts.audit_report as script
from app.audit_report import validate_audit_report_json
from app.authentication_keyring import HMAC_KEY_ENV_NAME, HMAC_KEY_ID_ENV_NAME
from app.authentication_trust import (
    AUTHENTICATION_TRUST_STORE_ENV_NAME,
    SINGLE_KEY_VALID_FROM_ENV_NAME,
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    AuditReportValidationError,
    AuthenticationExportError,
    ChecksumExportError,
    ReportArchiveExportError,
    ReportBundleExportError,
    ReportExportWriteError,
)
from app.observability import AUDIT_SCHEMA_VERSION
from app.report_archive import archive_path_for, verify_report_archive
from app.report_authenticity import (
    authentication_path_for,
    verify_report_authenticity,
)
from app.report_bundle import manifest_path_for
from app.report_integrity import checksum_path_for, verify_report_integrity

PRIVATE_INPUT = "착석 상태를 자동으로 감지하고 장시간 착석 시 사용자에게 진동 알림"
HMAC_SECRET = b"s" * 32
HMAC_SECRET_B64 = base64.b64encode(HMAC_SECRET).decode("ascii")
HMAC_KEY_ID = "key-1"
OLD_HMAC_SECRET = b"o" * 32
NEW_HMAC_SECRET = b"n" * 32
VALID_FROM = "2020-01-01T00:00:00+00:00"
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
SECRET_VALUES = (
    "sk-test-do-not-log",
    PRIVATE_INPUT,
    "PRIVATE-SUMMARY",
    "PRIVATE-REVIEW-REASON",
    "PRIVATE-ERROR-MESSAGE",
    "PRIVATE-TIMESTAMP",
)


def success_event(
    *,
    model: str = "gpt-test",
    timestamp_utc: str = "2026-08-02T00:00:00+00:00",
) -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_completed",
        "timestamp_utc": timestamp_utc,
        "status": "success",
        "model": model,
        "attempts": 1,
        "correction_attempted": False,
        "recorded_usage": {
            "input_tokens": 1,
            "cached_input_tokens": 0,
            "output_tokens": 2,
            "reasoning_tokens": 0,
            "total_tokens": 3,
        },
        "total_elapsed_seconds": 0.25,
        "response_ids": ["resp-private"],
        "final_response_id": "resp-private",
        "final_request_id": "req-private",
        "budget": {
            "max_attempts": 2,
            "max_recorded_tokens": 2000,
            "max_elapsed_seconds": 30.0,
        },
        "keyword_count": 1,
        "requires_review": False,
        "review_reason_present": False,
    }


def failure_event(
    *,
    model: str = "gpt-test",
    timestamp_utc: str = "2026-08-02T00:01:00+00:00",
) -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_failed",
        "timestamp_utc": timestamp_utc,
        "status": "failure",
        "model": model,
        "error_type": "RuntimeError",
        "recovery_action": "abort",
        "retryable": False,
        "budget": {
            "max_attempts": 2,
            "max_recorded_tokens": 2000,
            "max_elapsed_seconds": 30.0,
        },
    }







def trust_store_json(active_key_id: str = "new-key") -> str:
    old_status = "active" if active_key_id == "old-key" else "verify_only"
    new_status = "active" if active_key_id == "new-key" else "verify_only"
    return json.dumps(
        {
            "keys": [
                {
                    "key_id": "old-key",
                    "secret_b64": base64.b64encode(OLD_HMAC_SECRET).decode("ascii"),
                    "status": old_status,
                    "valid_from": VALID_FROM,
                    "valid_until": None,
                    "revoked_at": None,
                },
                {
                    "key_id": "new-key",
                    "secret_b64": base64.b64encode(NEW_HMAC_SECRET).decode("ascii"),
                    "status": new_status,
                    "valid_from": VALID_FROM,
                    "valid_until": None,
                    "revoked_at": None,
                },
            ],
        }
    )


def revoked_trust_store_json(*, revoked_at: str) -> str:
    return json.dumps(
        {
            "keys": [
                {
                    "key_id": HMAC_KEY_ID,
                    "secret_b64": HMAC_SECRET_B64,
                    "status": "revoked",
                    "valid_from": VALID_FROM,
                    "valid_until": None,
                    "revoked_at": revoked_at,
                }
            ],
        }
    )


def configure_authentication_keyring(
    monkeypatch: pytest.MonkeyPatch,
    *,
    active_key_id: str = "new-key",
) -> None:
    monkeypatch.setenv(AUTHENTICATION_TRUST_STORE_ENV_NAME, trust_store_json(active_key_id))


def runtime_keyring() -> AuthenticationTrustStore:
    return AuthenticationTrustStore(
        keys=(
            TrustedAuthenticationKey(
                "old-key",
                OLD_HMAC_SECRET,
                AuthenticationKeyStatus.VERIFY_ONLY,
                datetime.fromisoformat(VALID_FROM),
            ),
            TrustedAuthenticationKey(
                "new-key",
                NEW_HMAC_SECRET,
                AuthenticationKeyStatus.ACTIVE,
                datetime.fromisoformat(VALID_FROM),
            ),
        )
    )


def configure_authentication_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HMAC_KEY_ENV_NAME, HMAC_SECRET_B64)
    monkeypatch.setenv(HMAC_KEY_ID_ENV_NAME, HMAC_KEY_ID)
    monkeypatch.setenv(SINGLE_KEY_VALID_FROM_ENV_NAME, VALID_FROM)


def write_jsonl(path: Path, *events: dict[str, object]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )


def configure_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *events: dict[str, object],
) -> Path:
    path = tmp_path / "audit.jsonl"
    write_jsonl(path, *events)
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)
    return path


def valid_json_for_script() -> str:
    from app.audit_report import (
        ParsedAuditEvents,
        build_audit_report,
        format_audit_report_json,
    )

    return format_audit_report_json(build_audit_report(ParsedAuditEvents(successes=(), failures=())))


def run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str] | None = None,
) -> int:
    configure_log(
        monkeypatch,
        tmp_path,
        success_event(model="gpt-test", timestamp_utc="2026-08-02T00:00:00+00:00"),
        failure_event(model="gpt-test", timestamp_utc="2026-08-02T00:01:00+00:00"),
        success_event(model="gpt-other", timestamp_utc="2026-08-02T00:02:00+00:00"),
    )
    return script.main(argv)


def test_main_valid_log_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event())

    assert script.main([]) == 0
    assert "Structured Analysis Audit Report" in capsys.readouterr().out
    assert path.exists()


def test_main_outputs_report_title_and_sections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    script.main([])
    output = capsys.readouterr().out

    assert "Structured Analysis Audit Report" in output
    assert "Filters" in output
    assert "Summary" in output
    assert "Models" in output


def test_main_empty_log_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main([]) == 0


def test_main_invalid_log_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main([]) == 5


def test_main_invalid_log_outputs_abort_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main([])

    assert "Action: abort" in capsys.readouterr().out


def test_main_invalid_log_outputs_retryable_false(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main([])

    assert "Retryable: false" in capsys.readouterr().out


def test_main_invalid_log_outputs_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main([])

    assert "Reason:" in capsys.readouterr().out


def test_main_error_output_omits_raw_log_and_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE sk-test-do-not-log\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main([])
    output = capsys.readouterr().out

    for secret in SECRET_VALUES:
        assert secret not in output


def test_script_does_not_create_openai_client_or_load_env() -> None:
    assert not hasattr(script, "load_settings")
    assert not hasattr(script, "create_openai_client")


def test_main_does_not_modify_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event())
    before = path.read_text(encoding="utf-8")

    script.main([])

    assert path.read_text(encoding="utf-8") == before


def test_main_without_arguments_reports_all_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main(monkeypatch, tmp_path, []) == 0

    output = capsys.readouterr().out
    assert "Total Events: 3" in output
    assert "Status: all" in output


def test_main_since_argument_filters_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--since", "2026-08-02T00:01:00+00:00"])

    output = capsys.readouterr().out
    assert "Total Events: 2" in output
    assert "Since: 2026-08-02T00:01:00+00:00" in output


def test_main_until_argument_filters_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--until", "2026-08-02T00:01:00+00:00"])

    assert "Total Events: 1" in capsys.readouterr().out


def test_main_model_argument_filters_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--model", "gpt-other"])

    output = capsys.readouterr().out
    assert "Total Events: 1" in output
    assert "Model: gpt-other" in output


def test_main_status_success_filters_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--status", "success"])

    output = capsys.readouterr().out
    assert "Successes: 2" in output
    assert "Failures: 0" in output
    assert "Status: success" in output


def test_main_status_failure_filters_successes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--status", "failure"])

    output = capsys.readouterr().out
    assert "Successes: 0" in output
    assert "Failures: 1" in output
    assert "Status: failure" in output


def test_main_combined_filters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(
        monkeypatch,
        tmp_path,
        [
            "--since",
            "2026-08-02T00:01:00+00:00",
            "--until",
            "2026-08-02T00:03:00+00:00",
            "--model",
            "gpt-test",
            "--status",
            "failure",
        ],
    )

    output = capsys.readouterr().out
    assert "Total Events: 1" in output
    assert "Failures: 1" in output


def test_main_success_filter_excludes_failure_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--status", "success"])

    assert "Failures: 0" in capsys.readouterr().out


def test_main_failure_filter_excludes_success_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--status", "failure"])

    assert "Successes: 0" in capsys.readouterr().out


def test_main_model_filter_uses_exact_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--model", "gpt"])

    assert "Total Events: 0" in capsys.readouterr().out


def test_main_since_boundary_is_included(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--since", "2026-08-02T00:00:00+00:00"])

    assert "Total Events: 3" in capsys.readouterr().out


def test_main_until_boundary_is_excluded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--until", "2026-08-02T00:00:00+00:00"])

    assert "Total Events: 0" in capsys.readouterr().out


def test_main_empty_filtered_result_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main(monkeypatch, tmp_path, ["--model", "missing-model"]) == 0

    assert "Total Events: 0" in capsys.readouterr().out


def test_main_invalid_status_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--status", "invalid-status"])

    assert exc_info.value.code == 2


def test_main_invalid_iso_datetime_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--since", "not-a-date"])

    assert exc_info.value.code == 2


def test_main_naive_datetime_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--since", "2026-08-02T00:00:00"])

    assert exc_info.value.code == 2


def test_main_empty_model_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--model", "   "])

    assert exc_info.value.code == 2


def test_main_same_since_until_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main([
            "--since",
            "2026-08-02T00:00:00+00:00",
            "--until",
            "2026-08-02T00:00:00+00:00",
        ])

    assert exc_info.value.code == 2


def test_main_since_after_until_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main([
            "--since",
            "2026-08-02T00:01:00+00:00",
            "--until",
            "2026-08-02T00:00:00+00:00",
        ])

    assert exc_info.value.code == 2


def test_argparse_error_omits_raw_sensitive_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        script.main(["--since", "PRIVATE-TIMESTAMP"])

    assert "PRIVATE-TIMESTAMP" not in capsys.readouterr().err


def test_main_does_not_modify_log_with_filters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event(), failure_event())
    before = path.read_text(encoding="utf-8")

    script.main(["--status", "success"])

    assert path.read_text(encoding="utf-8") == before


def test_script_does_not_create_openai_client() -> None:
    assert not hasattr(script, "create_openai_client")


def test_script_does_not_load_settings() -> None:
    assert not hasattr(script, "load_settings")


def test_script_does_not_access_env_helpers() -> None:
    assert "dotenv" not in script.__dict__



def json_output(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)


def test_default_format_is_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, [])

    assert "Structured Analysis Audit Report" in capsys.readouterr().out


def test_format_text_outputs_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "text"])

    assert "Structured Analysis Audit Report" in capsys.readouterr().out


def test_format_json_outputs_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main(monkeypatch, tmp_path, ["--format", "json"]) == 0

    assert json_output(capsys)["report_type"] == "structured_analysis_audit_report"


def test_json_stdout_is_entirely_loadable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    json.loads(capsys.readouterr().out)


def test_json_stdout_schema_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    assert json_output(capsys)["schema_version"] == 1


def test_json_stdout_report_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    assert json_output(capsys)["report_type"] == "structured_analysis_audit_report"


def test_json_stdout_summary_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    summary = json_output(capsys)["summary"]
    assert summary["total_events"] == 3
    assert summary["success_count"] == 2
    assert summary["failure_count"] == 1


def test_json_status_success_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json", "--status", "success"])

    payload = json_output(capsys)
    assert payload["filters"]["status"] == "success"
    assert payload["summary"]["failure_count"] == 0


def test_json_status_failure_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json", "--status", "failure"])

    payload = json_output(capsys)
    assert payload["filters"]["status"] == "failure"
    assert payload["summary"]["success_count"] == 0


def test_json_model_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json", "--model", "gpt-other"])

    payload = json_output(capsys)
    assert payload["filters"]["model"] == "gpt-other"
    assert payload["summary"]["total_events"] == 1


def test_json_period_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(
        monkeypatch,
        tmp_path,
        [
            "--format",
            "json",
            "--since",
            "2026-08-02T00:01:00+00:00",
            "--until",
            "2026-08-02T00:03:00+00:00",
        ],
    )

    payload = json_output(capsys)
    assert payload["filters"]["since"] == "2026-08-02T00:01:00+00:00"
    assert payload["filters"]["until"] == "2026-08-02T00:03:00+00:00"
    assert payload["summary"]["total_events"] == 2


def test_json_combined_filter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(
        monkeypatch,
        tmp_path,
        [
            "--format",
            "json",
            "--since",
            "2026-08-02T00:01:00+00:00",
            "--model",
            "gpt-test",
            "--status",
            "failure",
        ],
    )

    payload = json_output(capsys)
    assert payload["summary"]["total_events"] == 1
    assert payload["summary"]["failure_count"] == 1


def test_json_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json", "--model", "missing-model"])

    assert json_output(capsys)["summary"]["total_events"] == 0


def test_invalid_format_exits_with_code_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--format", "yaml"])

    assert exc_info.value.code == 2


def test_json_output_has_no_text_header(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    output = capsys.readouterr().out
    assert "Structured Analysis Audit Report" not in output
    assert output.lstrip().startswith("{")


def test_json_output_has_no_ok_marker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    assert "[OK]" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "forbidden",
    [
        "resp-private",
        "req-private",
        "PRIVATE-SUMMARY",
        "PRIVATE-KEYWORD",
        "PRIVATE-REVIEW-REASON",
        "PRIVATE-ERROR-MESSAGE",
        "sk-test-do-not-log",
    ],
)
def test_json_output_omits_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    forbidden: str,
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    assert forbidden not in capsys.readouterr().out


def test_audit_log_error_keeps_exit_code_five_for_json_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main(["--format", "json"]) == 5


def test_audit_log_error_output_stays_text_for_json_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main(["--format", "json"])
    output = capsys.readouterr().out

    assert "[ERROR] Audit report generation failed" in output
    assert "Action: abort" in output


def test_json_format_does_not_modify_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event(), failure_event())
    before = path.read_text(encoding="utf-8")

    script.main(["--format", "json"])

    assert path.read_text(encoding="utf-8") == before


def test_json_script_does_not_create_openai_client() -> None:
    assert not hasattr(script, "create_openai_client")


def test_json_script_does_not_load_settings() -> None:
    assert not hasattr(script, "load_settings")


def test_json_script_does_not_access_env() -> None:
    assert "dotenv" not in script.__dict__



def test_script_json_payload_passes_contract_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    payload = validate_audit_report_json(capsys.readouterr().out)

    assert payload.report_type == "structured_analysis_audit_report"


def test_script_json_top_level_contract_is_stable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    payload = json.loads(capsys.readouterr().out)

    assert list(payload) == [
        "schema_version",
        "report_type",
        "filters",
        "summary",
        "correction",
        "recorded_usage",
        "latency",
        "failures",
        "errors_by_type",
        "recovery_actions",
        "models",
    ]


def test_script_payload_validation_failure_returns_exit_code_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def raise_validation_error(**kwargs: object) -> str:
        raise AuditReportValidationError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(script, "render_audit_report", raise_validation_error)

    assert script.main(["--format", "json"]) == 5


def test_script_payload_validation_failure_outputs_abort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def raise_validation_error(**kwargs: object) -> str:
        raise AuditReportValidationError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(script, "render_audit_report", raise_validation_error)

    script.main(["--format", "json"])
    output = capsys.readouterr().out

    assert "Action: abort" in output
    assert "Retryable: false" in output


def test_script_payload_validation_failure_omits_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def raise_validation_error(**kwargs: object) -> str:
        raise AuditReportValidationError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(script, "render_audit_report", raise_validation_error)

    script.main(["--format", "json"])

    assert "PRIVATE-ERROR-MESSAGE" not in capsys.readouterr().out


def test_script_payload_validation_failure_does_not_modify_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event())
    before = path.read_text(encoding="utf-8")

    def raise_validation_error(**kwargs: object) -> str:
        raise AuditReportValidationError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(script, "render_audit_report", raise_validation_error)
    script.main(["--format", "json"])

    assert path.read_text(encoding="utf-8") == before


def test_json_output_can_be_exported_to_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "reports" / "audit-report.json"

    assert run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)]) == 0

    assert output_path.is_file()


def test_json_output_export_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"

    assert run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)]) == 0


def test_json_output_export_creates_parent_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nested" / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert output_path.parent.is_dir()


def test_json_output_export_file_passes_contract_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    validate_audit_report_json(output_path.read_text(encoding="utf-8"))


def test_json_output_export_prints_success_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    output = capsys.readouterr().out

    assert "Audit report exported successfully." in output
    assert f"Output: {output_path}" in output


def test_json_output_export_does_not_print_full_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    output = capsys.readouterr().out

    assert not output.lstrip().startswith("{")
    assert '"schema_version"' not in output
    assert '"report_type"' not in output


def test_output_without_output_keeps_json_stdout_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_main(monkeypatch, tmp_path, ["--format", "json"])

    assert json.loads(capsys.readouterr().out)["report_type"] == "structured_analysis_audit_report"


def test_text_format_with_output_exits_with_code_two(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--format", "text", "--output", str(tmp_path / "report.json")])

    assert exc_info.value.code == 2


def test_output_with_default_text_format_exits_with_code_two(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--output", str(tmp_path / "report.json")])

    assert exc_info.value.code == 2


def test_invalid_output_extension_returns_exit_code_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.txt"

    assert run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)]) == 5


def test_export_write_failure_returns_exit_code_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def fail_export(**kwargs: object) -> None:
        raise ChecksumExportError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)

    assert script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json")]) == 5


def test_export_failure_outputs_abort_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def fail_export(**kwargs: object) -> None:
        raise ChecksumExportError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)
    script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json")])

    assert "Action: abort" in capsys.readouterr().out


def test_export_failure_outputs_retryable_false(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def fail_export(**kwargs: object) -> None:
        raise ReportExportWriteError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)
    script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json")])

    assert "Retryable: false" in capsys.readouterr().out


def test_export_failure_does_not_print_success_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())

    def fail_export(**kwargs: object) -> None:
        raise ReportExportWriteError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)
    script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json")])

    assert "Audit report exported successfully." not in capsys.readouterr().out


def test_export_failure_preserves_existing_target_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"
    output_path.write_text("existing", encoding="utf-8")

    def fail_export(**kwargs: object) -> None:
        raise ReportExportWriteError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)
    script.main(["--format", "json", "--output", str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "existing"


def test_export_does_not_modify_source_audit_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = configure_log(monkeypatch, tmp_path, success_event(), failure_event())
    before = path.read_text(encoding="utf-8")

    script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json")])

    assert path.read_text(encoding="utf-8") == before


def test_export_uses_tmp_path_not_project_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "reports" / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert output_path.exists()
    assert not (script.PROJECT_ROOT / "reports" / "audit-report.json").exists()


def test_export_script_does_not_create_openai_client() -> None:
    assert not hasattr(script, "create_openai_client")


def test_export_script_does_not_load_settings() -> None:
    assert not hasattr(script, "load_settings")


def test_export_script_does_not_access_env() -> None:
    assert "dotenv" not in script.__dict__


def test_json_output_export_creates_checksum_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert checksum_path_for(output_path).is_file()


def test_json_output_export_checksum_verifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    verify_report_integrity(report_path=output_path)


def test_json_output_export_prints_checksum_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert f"Checksum: {checksum_path_for(output_path)}" in capsys.readouterr().out


def test_json_output_export_prints_sha256_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"

    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert "SHA-256:" in capsys.readouterr().out


def test_checksum_generation_failure_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"

    def fail_export(**kwargs: object) -> None:
        Path(kwargs["path"]).write_text("{}", encoding="utf-8")
        raise ReportExportWriteError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)

    assert script.main(["--format", "json", "--output", str(output_path)]) == 5


def test_checksum_generation_failure_keeps_json_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"

    def fail_export(**kwargs: object) -> None:
        Path(kwargs["path"]).write_text("{}", encoding="utf-8")
        raise ReportExportWriteError("PRIVATE-EXPORT-ERROR")

    monkeypatch.setattr(script, "export_json_report_with_checksum", fail_export)
    script.main(["--format", "json", "--output", str(output_path)])

    assert output_path.exists()


def test_verify_mode_success_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    assert script.main(["--verify", str(output_path)]) == 0


def test_verify_mode_outputs_success_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    capsys.readouterr()

    script.main(["--verify", str(output_path)])

    assert "Audit report integrity verified." in capsys.readouterr().out


def test_verify_mode_outputs_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    capsys.readouterr()

    script.main(["--verify", str(output_path)])

    assert "SHA-256:" in capsys.readouterr().out


def test_verify_mode_succeeds_without_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", tmp_path / "missing.jsonl")

    assert script.main(["--verify", str(output_path)]) == 0


def test_verify_mode_does_not_call_read_audit_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])

    def fail_read(*args: object, **kwargs: object) -> object:
        raise AssertionError("read_audit_events must not be called")

    monkeypatch.setattr(script, "read_audit_events", fail_read)

    assert script.main(["--verify", str(output_path)]) == 0


def test_verify_mode_changed_json_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    output_path.write_text(output_path.read_text(encoding="utf-8").replace("gpt-test", "gpt-tampered"), encoding="utf-8")

    assert script.main(["--verify", str(output_path)]) == 5


def test_verify_mode_bad_checksum_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    checksum_path_for(output_path).write_text(f"{'0' * 64}  audit-report.json\n", encoding="utf-8")

    assert script.main(["--verify", str(output_path)]) == 5


def test_verify_mode_missing_checksum_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    checksum_path_for(output_path).unlink()

    assert script.main(["--verify", str(output_path)]) == 5


@pytest.mark.parametrize(
    "argv",
    [
        ["--verify", "report.json", "--output", "out.json"],
        ["--verify", "report.json", "--since", "2026-08-02T00:00:00+00:00"],
        ["--verify", "report.json", "--until", "2026-08-02T00:00:00+00:00"],
        ["--verify", "report.json", "--model", "gpt-5"],
        ["--verify", "report.json", "--status", "success"],
        ["--verify", "report.json", "--format", "json"],
    ],
)
def test_verify_mode_rejects_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(argv)

    assert exc_info.value.code == 2


def test_verify_failure_header_is_specific(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    checksum_path_for(output_path).write_text(f"{'0' * 64}  audit-report.json\n", encoding="utf-8")
    capsys.readouterr()

    script.main(["--verify", str(output_path)])

    assert "[ERROR] Audit report integrity verification failed" in capsys.readouterr().out


def test_verify_failure_does_not_modify_report_or_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)])
    checksum_path = checksum_path_for(output_path)
    checksum_path.write_text(f"{'0' * 64}  audit-report.json\n", encoding="utf-8")
    report_before = output_path.read_text(encoding="utf-8")
    checksum_before = checksum_path.read_text(encoding="utf-8")

    script.main(["--verify", str(output_path)])

    assert output_path.read_text(encoding="utf-8") == report_before
    assert checksum_path.read_text(encoding="utf-8") == checksum_before




def test_authenticate_export_creates_json_checksum_and_hmac(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 0

    assert output_path.is_file()
    assert checksum_path_for(output_path).is_file()
    assert authentication_path_for(output_path).is_file()


def test_authenticate_export_hmac_verifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    verify_report_authenticity(
        report_path=output_path,
        trust_store=AuthenticationTrustStore(
            keys=(
                TrustedAuthenticationKey(
                    HMAC_KEY_ID,
                    HMAC_SECRET,
                    AuthenticationKeyStatus.ACTIVE,
                    datetime.fromisoformat(VALID_FROM),
                ),
            )
        ),
        verification_time=datetime.now(UTC),
    )


def test_authenticate_export_success_output_includes_authentication_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    output = capsys.readouterr().out

    assert "Algorithm: hmac-sha256-v2" in output
    assert f"Key ID: {HMAC_KEY_ID}" in output
    assert "Authenticated At:" in output
    assert "HMAC:" in output
    assert HMAC_SECRET_B64 not in output


def test_authenticate_export_sidecar_omits_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    sidecar = authentication_path_for(output_path).read_text(encoding="utf-8")
    assert HMAC_SECRET_B64 not in sidecar
    assert HMAC_SECRET.decode() not in sidecar


def test_authenticate_without_output_exits_with_code_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_authentication_key(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        script.main(["--format", "json", "--authenticate"])

    assert exc_info.value.code == 2


def test_authenticate_with_text_format_exits_with_code_two(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        script.main(["--format", "text", "--output", str(tmp_path / "report.json"), "--authenticate"])

    assert exc_info.value.code == 2


def test_authenticate_missing_key_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(HMAC_KEY_ENV_NAME, raising=False)
    monkeypatch.delenv(HMAC_KEY_ID_ENV_NAME, raising=False)
    monkeypatch.delenv(SINGLE_KEY_VALID_FROM_ENV_NAME, raising=False)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 5


def test_authenticate_invalid_key_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(HMAC_KEY_ENV_NAME, "not-base64!")
    monkeypatch.setenv(HMAC_KEY_ID_ENV_NAME, HMAC_KEY_ID)
    monkeypatch.setenv(SINGLE_KEY_VALID_FROM_ENV_NAME, VALID_FROM)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 5


def test_hmac_export_failure_keeps_json_and_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"

    def fail_export(**kwargs: object) -> None:
        Path(kwargs["path"]).write_text(valid_json_for_script(), encoding="utf-8")
        checksum_path_for(Path(kwargs["path"])).write_text(
            f"{'a' * 64}  audit-report.json\n",
            encoding="utf-8",
        )
        raise AuthenticationExportError("PRIVATE-HMAC-SECRET")

    monkeypatch.setattr(script, "export_json_report_bundle", fail_export)

    assert script.main(["--format", "json", "--output", str(output_path), "--authenticate"]) == 5
    assert output_path.exists()
    assert checksum_path_for(output_path).exists()


def test_hmac_export_failure_outputs_abort_without_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    configure_log(monkeypatch, tmp_path, success_event())

    def fail_export(**kwargs: object) -> None:
        raise AuthenticationExportError("PRIVATE-HMAC-SECRET")

    monkeypatch.setattr(script, "export_json_report_bundle", fail_export)
    script.main(["--format", "json", "--output", str(tmp_path / "audit-report.json"), "--authenticate"])
    output = capsys.readouterr().out

    assert "Action: abort" in output
    assert "Retryable: false" in output
    assert "Audit report exported successfully." not in output
    assert "PRIVATE-HMAC-SECRET" not in output


def test_verify_authenticity_success_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    assert script.main(["--verify-authenticity", str(output_path)]) == 0


def test_verify_authenticity_outputs_success_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    capsys.readouterr()

    script.main(["--verify-authenticity", str(output_path)])
    output = capsys.readouterr().out

    assert "Audit report authenticity verified." in output
    assert "Algorithm: hmac-sha256-v2" in output
    assert f"Key ID: {HMAC_KEY_ID}" in output
    assert "Authenticated At:" in output
    assert "HMAC:" in output
    assert HMAC_SECRET_B64 not in output


def test_verify_authenticity_succeeds_without_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", tmp_path / "missing.jsonl")

    assert script.main(["--verify-authenticity", str(output_path)]) == 0


def test_verify_authenticity_does_not_read_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    def fail_read(*args: object, **kwargs: object) -> object:
        raise AssertionError("read_audit_events must not be called")

    monkeypatch.setattr(script, "read_audit_events", fail_read)

    assert script.main(["--verify-authenticity", str(output_path)]) == 0


def test_verify_authenticity_changed_json_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    output_path.write_text(
        output_path.read_text(encoding="utf-8").replace("gpt-test", "gpt-x"),
        encoding="utf-8",
    )

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_verify_authenticity_different_secret_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    monkeypatch.setenv(HMAC_KEY_ENV_NAME, base64.b64encode(b"t" * 32).decode("ascii"))

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_verify_authenticity_unknown_key_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    monkeypatch.setenv(HMAC_KEY_ID_ENV_NAME, "other-key")

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_verify_authenticity_malformed_hmac_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    authentication_path_for(output_path).write_text("PRIVATE-HMAC-SECRET", encoding="utf-8")

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_verify_authenticity_missing_hmac_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    authentication_path_for(output_path).unlink()

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


@pytest.mark.parametrize(
    "argv",
    [
        ["--verify", "report.json", "--verify-authenticity", "report.json"],
        ["--verify-authenticity", "report.json", "--output", "out.json"],
        ["--verify-authenticity", "report.json", "--authenticate"],
        ["--verify-authenticity", "report.json", "--since", "2026-08-02T00:00:00+00:00"],
        ["--verify-authenticity", "report.json", "--until", "2026-08-02T00:00:00+00:00"],
        ["--verify-authenticity", "report.json", "--model", "gpt-5"],
        ["--verify-authenticity", "report.json", "--status", "success"],
        ["--verify-authenticity", "report.json", "--format", "json"],
        ["--verify-authenticity", "report.json", "--revoked-key-policy", "unknown"],
    ],
)
def test_verify_authenticity_rejects_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(argv)

    assert exc_info.value.code == 2


def test_revoked_key_policy_is_only_allowed_for_verify_authenticity() -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--revoked-key-policy", "allow_pre_revocation"])

    assert exc_info.value.code == 2


def test_verify_authenticity_failure_header_and_secret_omission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    authentication_path_for(output_path).write_text("PRIVATE-HMAC-SECRET", encoding="utf-8")
    capsys.readouterr()

    script.main(["--verify-authenticity", str(output_path)])
    output = capsys.readouterr().out

    assert "[ERROR] Audit report authenticity verification failed" in output
    assert "PRIVATE-HMAC-SECRET" not in output
    assert HMAC_SECRET_B64 not in output


def test_verify_authenticity_failure_does_not_modify_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    auth_path = authentication_path_for(output_path)
    auth_path.write_text("PRIVATE-HMAC-SECRET", encoding="utf-8")
    report_before = output_path.read_text(encoding="utf-8")
    auth_before = auth_path.read_text(encoding="utf-8")

    script.main(["--verify-authenticity", str(output_path)])

    assert output_path.read_text(encoding="utf-8") == report_before
    assert auth_path.read_text(encoding="utf-8") == auth_before


def test_authenticate_export_with_trust_store_uses_active_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_keyring(monkeypatch, active_key_id="new-key")
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 0
    output = capsys.readouterr().out

    assert "Key ID: new-key" in output
    assert "  new-key  " in authentication_path_for(output_path).read_text(encoding="utf-8")


def test_authenticate_export_trust_store_does_not_use_old_key_for_new_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_keyring(monkeypatch, active_key_id="new-key")
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    assert "  old-key  " not in authentication_path_for(output_path).read_text(encoding="utf-8")


def test_verify_authenticity_old_report_after_active_key_rotation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_keyring(monkeypatch, active_key_id="old-key")
    old_path = tmp_path / "old-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(old_path), "--authenticate"],
    )
    configure_authentication_keyring(monkeypatch, active_key_id="new-key")
    new_path = tmp_path / "new-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(new_path), "--authenticate"],
    )

    assert script.main(["--verify-authenticity", str(old_path)]) == 0
    assert "  old-key  " in authentication_path_for(old_path).read_text(encoding="utf-8")
    assert "  new-key  " in authentication_path_for(new_path).read_text(encoding="utf-8")


def test_verify_authenticity_unregistered_sidecar_key_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_keyring(monkeypatch, active_key_id="new-key")
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    authentication_path_for(output_path).write_text(
        authentication_path_for(output_path).read_text(encoding="utf-8").replace("new-key", "missing-key"),
        encoding="utf-8",
    )

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_authenticate_malformed_trust_store_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(AUTHENTICATION_TRUST_STORE_ENV_NAME, "{")

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(tmp_path / "report.json"), "--authenticate"],
    ) == 5


def test_authenticate_duplicate_trust_store_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "dup-key",
                        "secret_b64": base64.b64encode(HMAC_SECRET).decode("ascii"),
                        "status": "active",
                        "valid_from": VALID_FROM,
                        "valid_until": None,
                        "revoked_at": None,
                    },
                    {
                        "key_id": "dup-key",
                        "secret_b64": base64.b64encode(NEW_HMAC_SECRET).decode("ascii"),
                        "status": "active",
                        "valid_from": VALID_FROM,
                        "valid_until": None,
                        "revoked_at": None,
                    },
                ],
            }
        ),
    )

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(tmp_path / "report.json"), "--authenticate"],
    ) == 5


def test_authenticate_no_active_key_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "key-1",
                        "secret_b64": HMAC_SECRET_B64,
                        "status": "verify_only",
                        "valid_from": VALID_FROM,
                        "valid_until": None,
                        "revoked_at": None,
                    }
                ],
            }
        ),
    )

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(tmp_path / "report.json"), "--authenticate"],
    ) == 5


def test_trust_store_json_and_secrets_are_not_printed_on_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "PRIVATE-KEYRING-SECRET"
    payload = json.dumps(
        {
            "keys": [
                {
                    "key_id": "key-1",
                    "secret_b64": secret,
                    "status": "active",
                    "valid_from": VALID_FROM,
                    "valid_until": None,
                    "revoked_at": None,
                }
            ],
        }
    )
    monkeypatch.setenv(AUTHENTICATION_TRUST_STORE_ENV_NAME, payload)

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(tmp_path / "report.json"), "--authenticate"],
    )
    output = capsys.readouterr().out

    assert secret not in output
    assert payload not in output


def test_single_key_environment_remains_compatible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 0
    assert "  key-1  " in authentication_path_for(output_path).read_text(encoding="utf-8")


def test_trust_store_json_takes_precedence_over_single_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    configure_authentication_keyring(monkeypatch, active_key_id="new-key")
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    assert "  new-key  " in authentication_path_for(output_path).read_text(encoding="utf-8")
    assert "  key-1  " not in authentication_path_for(output_path).read_text(encoding="utf-8")


def test_bad_trust_store_json_does_not_fallback_to_single_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    monkeypatch.setenv(AUTHENTICATION_TRUST_STORE_ENV_NAME, "{")

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(tmp_path / "report.json"), "--authenticate"],
    ) == 5


def test_revoked_key_default_verify_policy_rejects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        revoked_trust_store_json(revoked_at="2100-01-01T00:00:00+00:00"),
    )

    assert script.main(["--verify-authenticity", str(output_path)]) == 5


def test_revoked_key_allow_pre_revocation_policy_accepts_old_signature(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        revoked_trust_store_json(revoked_at="2100-01-01T00:00:00+00:00"),
    )

    assert script.main(
        [
            "--verify-authenticity",
            str(output_path),
            "--revoked-key-policy",
            "allow_pre_revocation",
        ]
    ) == 0


def test_revoked_key_at_boundary_fails_even_with_allow_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    sidecar_text = authentication_path_for(output_path).read_text(encoding="utf-8")
    authenticated_at = sidecar_text.split("  ")[2]
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        revoked_trust_store_json(revoked_at=authenticated_at),
    )

    assert script.main(
        [
            "--verify-authenticity",
            str(output_path),
            "--revoked-key-policy",
            "allow_pre_revocation",
        ]
    ) == 5


def test_verify_authenticity_future_authentication_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2100, 1, 1, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(script, "datetime", FutureDateTime)
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )

    class PresentDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 8, 2, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(script, "datetime", PresentDateTime)

    assert script.main(["--verify-authenticity", str(output_path)]) == 5



def test_authenticate_export_creates_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    ) == 0

    assert manifest_path_for(output_path).is_file()


def test_authenticate_export_outputs_manifest_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate"],
    )
    output = capsys.readouterr().out

    assert f"Manifest: {manifest_path_for(output_path)}" in output
    assert "Manifest Version: 1" in output


def test_non_authenticated_export_does_not_create_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit-report.json"

    assert run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path)]) == 0

    assert not manifest_path_for(output_path).exists()


def test_manifest_export_failure_returns_five_and_keeps_three_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"

    def fail_bundle_export(**kwargs: object) -> None:
        path = Path(kwargs["path"])
        path.write_text(valid_json_for_script(), encoding="utf-8")
        checksum_path_for(path).write_text(f"{'a' * 64}  {path.name}\n", encoding="utf-8")
        authentication_path_for(path).write_text("PRIVATE-HMAC-SIDECAR", encoding="utf-8")
        raise ReportBundleExportError("PRIVATE-BUNDLE-ERROR")

    monkeypatch.setattr(script, "export_json_report_bundle", fail_bundle_export)

    assert script.main(["--format", "json", "--output", str(output_path), "--authenticate"]) == 5
    output = capsys.readouterr().out

    assert output_path.exists()
    assert checksum_path_for(output_path).exists()
    assert authentication_path_for(output_path).exists()
    assert not manifest_path_for(output_path).exists()
    assert "Audit report exported successfully." not in output
    assert "Action: abort" in output
    assert "Retryable: false" in output
    assert "PRIVATE-BUNDLE-ERROR" not in output


def test_verify_bundle_success_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])

    assert script.main(["--verify-bundle", str(output_path)]) == 0


def test_verify_bundle_outputs_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    capsys.readouterr()

    script.main(["--verify-bundle", str(output_path)])
    output = capsys.readouterr().out

    assert "Audit report bundle verified." in output
    assert f"Manifest: {manifest_path_for(output_path)}" in output
    assert "Manifest Version: 1" in output
    assert "Report Schema Version: 1" in output
    assert "Authentication Protocol Version: 2" in output
    assert "Algorithm: hmac-sha256-v2" in output
    assert f"Key ID: {HMAC_KEY_ID}" in output
    assert "Authenticated At:" in output


def test_verify_bundle_succeeds_without_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", tmp_path / "missing.jsonl")

    assert script.main(["--verify-bundle", str(output_path)]) == 0


def test_verify_bundle_does_not_read_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])

    def fail_read(*args: object, **kwargs: object) -> object:
        raise AssertionError("read_audit_events must not be called")

    monkeypatch.setattr(script, "read_audit_events", fail_read)

    assert script.main(["--verify-bundle", str(output_path)]) == 0


@pytest.mark.parametrize(
    "mutate",
    ["json", "checksum", "hmac", "manifest"],
)
def test_verify_bundle_detects_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutate: str,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    if mutate == "json":
        output_path.write_text(output_path.read_text(encoding="utf-8").replace("gpt-test", "gpt-x"), encoding="utf-8")
    elif mutate == "checksum":
        checksum_path_for(output_path).write_text(f"{'0' * 64}  {output_path.name}\n", encoding="utf-8")
    elif mutate == "hmac":
        authentication_path_for(output_path).write_text("invalid", encoding="utf-8")
    else:
        manifest_path_for(output_path).write_text("invalid", encoding="utf-8")

    assert script.main(["--verify-bundle", str(output_path)]) == 5


def test_verify_bundle_missing_manifest_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    manifest_path_for(output_path).unlink()

    assert script.main(["--verify-bundle", str(output_path)]) == 5


@pytest.mark.parametrize(
    "argv",
    [
        ["--verify", "report.json", "--verify-bundle", "report.json"],
        ["--verify-authenticity", "report.json", "--verify-bundle", "report.json"],
        ["--verify-bundle", "report.json", "--output", "out.json"],
        ["--verify-bundle", "report.json", "--authenticate"],
        ["--verify-bundle", "report.json", "--since", "2026-08-02T00:00:00+00:00"],
        ["--verify-bundle", "report.json", "--until", "2026-08-02T00:00:00+00:00"],
        ["--verify-bundle", "report.json", "--model", "gpt-5"],
        ["--verify-bundle", "report.json", "--status", "success"],
        ["--verify-bundle", "report.json", "--format", "json"],
    ],
)
def test_verify_bundle_rejects_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(argv)

    assert exc_info.value.code == 2


def test_verify_bundle_passes_revoked_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    sidecar_text = authentication_path_for(output_path).read_text(encoding="utf-8")
    authenticated_at = sidecar_text.split("  ")[2]
    monkeypatch.setenv(
        AUTHENTICATION_TRUST_STORE_ENV_NAME,
        revoked_trust_store_json(revoked_at="2100-01-01T00:00:00+00:00"),
    )

    assert script.main(
        [
            "--verify-bundle",
            str(output_path),
            "--revoked-key-policy",
            "allow_pre_revocation",
        ]
    ) == 0
    assert authenticated_at in authentication_path_for(output_path).read_text(encoding="utf-8")


def test_verify_bundle_failure_header_and_secret_omission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(monkeypatch, tmp_path, ["--format", "json", "--output", str(output_path), "--authenticate"])
    manifest_path_for(output_path).write_text("PRIVATE-BUNDLE-ERROR", encoding="utf-8")
    capsys.readouterr()

    script.main(["--verify-bundle", str(output_path)])
    output = capsys.readouterr().out

    assert "[ERROR] Audit report bundle verification failed" in output
    assert "Action: abort" in output
    assert "Retryable: false" in output
    assert "PRIVATE-BUNDLE-ERROR" not in output
    assert HMAC_SECRET_B64 not in output

def test_archive_export_creates_zip_and_outputs_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    ) == 0
    output = capsys.readouterr().out

    assert archive_path_for(output_path).is_file()
    assert "Archive:" in output
    assert "Archive Format Version: 1" in output
    assert "Archive Members: 4" in output
    assert "Archive SHA-256:" in output


def test_archive_export_zip_verifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"

    assert run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    ) == 0

    assert verify_report_archive(
        archive_path=archive_path_for(output_path),
        trust_store=AuthenticationTrustStore(
            keys=(
                TrustedAuthenticationKey(
                    HMAC_KEY_ID,
                    HMAC_SECRET,
                    AuthenticationKeyStatus.ACTIVE,
                    datetime.fromisoformat(VALID_FROM),
                ),
            )
        ),
        verification_time=datetime.now(UTC),
    ).member_count == 4


@pytest.mark.parametrize(
    "argv",
    [
        ["--format", "json", "--authenticate", "--archive"],
        ["--format", "json", "--output", "out.json", "--archive"],
        ["--output", "out.json", "--authenticate", "--archive"],
        ["--verify", "report.json", "--archive"],
    ],
)
def test_archive_export_rejects_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(argv)

    assert exc_info.value.code == 2


def test_archive_export_failure_keeps_bundle_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    configure_log(monkeypatch, tmp_path, success_event())
    output_path = tmp_path / "audit-report.json"

    def fail_archive(**kwargs: object) -> None:
        from app.report_export import export_json_report_bundle

        export_json_report_bundle(
            path=kwargs["path"],
            json_text=kwargs["json_text"],
            trust_store=kwargs["trust_store"],
            authenticated_at=kwargs["authenticated_at"],
        )
        raise ReportArchiveExportError("PRIVATE-ARCHIVE-ERROR")

    monkeypatch.setattr(script, "export_json_report_archive", fail_archive)

    assert script.main(["--format", "json", "--output", str(output_path), "--authenticate", "--archive"]) == 5
    output = capsys.readouterr().out

    assert output_path.exists()
    assert checksum_path_for(output_path).exists()
    assert authentication_path_for(output_path).exists()
    assert manifest_path_for(output_path).exists()
    assert not archive_path_for(output_path).exists()
    assert "Audit report exported successfully." not in output
    assert "Action: abort" in output
    assert "Retryable: false" in output
    assert "PRIVATE-ARCHIVE-ERROR" not in output


def test_verify_archive_success_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    )

    assert script.main(["--verify-archive", str(archive_path_for(output_path))]) == 0
    output = capsys.readouterr().out

    assert "Audit report archive verified." in output
    assert "Archive Format Version: 1" in output
    assert "Archive SHA-256:" in output
    assert "Members: 4" in output
    assert "Manifest Version: 1" in output
    assert "Report Schema Version: 1" in output
    assert "Authentication Protocol Version: 2" in output
    assert "Algorithm: hmac-sha256-v2" in output
    assert "Key ID:" in output
    assert "Authenticated At:" in output
    assert "Report Filename: audit-report.json" in output


def test_verify_archive_succeeds_without_audit_log_or_external_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    )
    archive_path = archive_path_for(output_path)
    for path in (output_path, checksum_path_for(output_path), authentication_path_for(output_path), manifest_path_for(output_path)):
        path.unlink()
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", tmp_path / "missing.jsonl")

    assert script.main(["--verify-archive", str(archive_path)]) == 0


def test_verify_archive_does_not_call_read_audit_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    )

    def fail_read(*args: object, **kwargs: object) -> None:
        raise AssertionError("read_audit_events must not be called")

    monkeypatch.setattr(script, "read_audit_events", fail_read)

    assert script.main(["--verify-archive", str(archive_path_for(output_path))]) == 0


def test_verify_archive_tamper_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_authentication_key(monkeypatch)
    output_path = tmp_path / "audit-report.json"
    run_main(
        monkeypatch,
        tmp_path,
        ["--format", "json", "--output", str(output_path), "--authenticate", "--archive"],
    )
    archive_path = archive_path_for(output_path)
    with ZipFile(archive_path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("extra.txt", b"PRIVATE-ARCHIVE-ERROR")

    assert script.main(["--verify-archive", str(archive_path)]) == 5


@pytest.mark.parametrize(
    "argv",
    [
        ["--verify", "report.json", "--verify-archive", "report.bundle.zip"],
        ["--verify-authenticity", "report.json", "--verify-archive", "report.bundle.zip"],
        ["--verify-bundle", "report.json", "--verify-archive", "report.bundle.zip"],
        ["--verify-archive", "report.bundle.zip", "--output", "out.json"],
        ["--verify-archive", "report.bundle.zip", "--archive"],
        ["--verify-archive", "report.bundle.zip", "--format", "json"],
        ["--verify-archive", "report.bundle.zip", "--status", "success"],
    ],
)
def test_verify_archive_rejects_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        script.main(argv)

    assert exc_info.value.code == 2


def test_verify_archive_failure_header_and_secret_omission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_authentication_key(monkeypatch)
    archive_path = tmp_path / "audit-report.bundle.zip"
    archive_path.write_bytes(b"PRIVATE-ARCHIVE-ERROR")

    assert script.main(["--verify-archive", str(archive_path)]) == 5
    output = capsys.readouterr().out

    assert "[ERROR] Audit report archive verification failed" in output
    assert "Action: abort" in output
    assert "Retryable: false" in output
    assert "PRIVATE-ARCHIVE-ERROR" not in output
    assert HMAC_SECRET_B64 not in output
