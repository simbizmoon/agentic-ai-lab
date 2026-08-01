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
)


def success_event() -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_completed",
        "timestamp_utc": "2026-08-02T00:00:00+00:00",
        "status": "success",
        "model": "gpt-test",
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


def write_jsonl(path: Path, *events: dict[str, object]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )


def test_main_valid_log_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    write_jsonl(path, success_event())
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main() == 0
    assert "Structured Analysis Audit Report" in capsys.readouterr().out


def test_main_outputs_report_title_and_sections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    write_jsonl(path, success_event())
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()
    output = capsys.readouterr().out

    assert "Structured Analysis Audit Report" in output
    assert "Summary" in output
    assert "Models" in output


def test_main_empty_log_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main() == 0


def test_main_invalid_log_returns_five(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    assert script.main() == 5


def test_main_invalid_log_outputs_abort_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()

    assert "Action: abort" in capsys.readouterr().out


def test_main_invalid_log_outputs_retryable_false(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()

    assert "Retryable: false" in capsys.readouterr().out


def test_main_invalid_log_outputs_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()

    assert "Reason:" in capsys.readouterr().out


def test_main_error_output_omits_raw_log_and_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE sk-test-do-not-log\n", encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()
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
    path = tmp_path / "audit.jsonl"
    write_jsonl(path, success_event())
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(script, "AUDIT_LOG_PATH", path)

    script.main()

    assert path.read_text(encoding="utf-8") == before
