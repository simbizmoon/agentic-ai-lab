from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.audit_report as script
from app.audit_report import validate_audit_report_json
from app.exceptions import (
    AuditReportValidationError,
    ChecksumExportError,
    ReportExportWriteError,
)
from app.observability import AUDIT_SCHEMA_VERSION
from app.report_integrity import checksum_path_for, verify_report_integrity

PRIVATE_INPUT = "착석 상태를 자동으로 감지하고 장시간 착석 시 사용자에게 진동 알림"
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
