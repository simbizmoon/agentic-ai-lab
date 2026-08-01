from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.audit_report as script
from app.observability import AUDIT_SCHEMA_VERSION

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
