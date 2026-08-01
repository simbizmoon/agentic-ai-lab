from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.budget import ExecutionBudget
from app.exceptions import AuditLogError
from app.observability import (
    AUDIT_SCHEMA_VERSION,
    AuditBudget,
    AuditTokenUsage,
    append_audit_event,
    build_failure_event,
    build_success_event,
    current_utc_timestamp,
    to_audit_budget,
    to_audit_token_usage,
)
from app.recovery import RecoveryAction, RecoveryDecision
from app.schemas.text_analysis import Sentiment, TextAnalysis
from app.services.structured_analysis import (
    StructuredAnalysisExecution,
    StructuredAnalysisResult,
)
from app.services.text_generation import TokenUsage

SECRET_TEXTS = (
    "sk-test-do-not-log",
    "CONFIDENTIAL-PATENT-IDEA",
    "PRIVATE-MODEL-SUMMARY",
    "PRIVATE-KEYWORD",
    "PRIVATE-REVIEW-REASON",
    "PRIVATE-ERROR-MESSAGE",
)


def make_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_attempts=2,
        max_recorded_tokens=2000,
        max_elapsed_seconds=30.0,
    )


def make_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=10,
        cached_input_tokens=1,
        output_tokens=20,
        reasoning_tokens=2,
        total_tokens=30,
    )


def make_execution() -> StructuredAnalysisExecution:
    analysis = TextAnalysis(
        topic="CONFIDENTIAL-PATENT-IDEA",
        summary="PRIVATE-MODEL-SUMMARY",
        sentiment=Sentiment.NEUTRAL,
        keywords=["PRIVATE-KEYWORD"],
        requires_review=True,
        review_reason="PRIVATE-REVIEW-REASON",
    )
    result = StructuredAnalysisResult(
        analysis=analysis,
        response_id="resp_test",
        request_id="req_test",
        usage=make_usage(),
        elapsed_seconds=0.25,
    )
    return StructuredAnalysisExecution(
        result=result,
        attempts=2,
        correction_attempted=True,
        total_usage=make_usage(),
        total_elapsed_seconds=0.75,
        response_ids=("resp_first", "resp_test"),
    )


def make_success_event():
    return build_success_event(
        model="test-model",
        execution=make_execution(),
        budget=make_budget(),
        timestamp_utc="2026-08-01T00:00:00+00:00",
    )


def make_failure_event():
    return build_failure_event(
        model="test-model",
        error=RuntimeError("PRIVATE-ERROR-MESSAGE"),
        decision=RecoveryDecision(
            retryable=False,
            action=RecoveryAction.ABORT,
            reason="stable reason",
        ),
        budget=make_budget(),
        timestamp_utc="2026-08-01T00:00:00+00:00",
    )


def assert_no_secret(value: object) -> None:
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    for secret_text in SECRET_TEXTS:
        assert secret_text not in encoded


def test_current_utc_timestamp_includes_utc_offset() -> None:
    assert current_utc_timestamp().endswith("+00:00")


def test_to_audit_token_usage_converts_usage() -> None:
    assert to_audit_token_usage(make_usage()) == AuditTokenUsage(
        input_tokens=10,
        cached_input_tokens=1,
        output_tokens=20,
        reasoning_tokens=2,
        total_tokens=30,
    )


def test_to_audit_token_usage_allows_none() -> None:
    assert to_audit_token_usage(None) is None


def test_to_audit_budget_converts_budget() -> None:
    assert to_audit_budget(make_budget()) == AuditBudget(
        max_attempts=2,
        max_recorded_tokens=2000,
        max_elapsed_seconds=30.0,
    )


def test_success_event_has_fixed_fields() -> None:
    event = make_success_event()

    assert event.schema_version == AUDIT_SCHEMA_VERSION
    assert event.event_type == "structured_analysis_completed"
    assert event.status == "success"


def test_success_event_records_execution_metadata() -> None:
    event = make_success_event()

    assert event.attempts == 2
    assert event.correction_attempted is True
    assert event.recorded_usage == to_audit_token_usage(make_usage())
    assert event.total_elapsed_seconds == 0.75
    assert event.response_ids == ("resp_first", "resp_test")
    assert event.final_response_id == "resp_test"
    assert event.final_request_id == "req_test"


def test_success_event_records_keyword_count() -> None:
    assert make_success_event().keyword_count == 1


def test_success_event_records_requires_review() -> None:
    assert make_success_event().requires_review is True


def test_success_event_records_review_reason_presence() -> None:
    assert make_success_event().review_reason_present is True


def test_success_event_does_not_record_topic() -> None:
    payload = asdict(make_success_event())

    assert "topic" not in payload
    assert_no_secret(payload)


def test_success_event_does_not_record_summary() -> None:
    payload = asdict(make_success_event())

    assert "summary" not in payload
    assert_no_secret(payload)


def test_success_event_does_not_record_keyword_values() -> None:
    assert_no_secret(asdict(make_success_event()))


def test_success_event_does_not_record_review_reason_value() -> None:
    assert_no_secret(asdict(make_success_event()))


def test_failure_event_has_fixed_fields() -> None:
    event = make_failure_event()

    assert event.schema_version == AUDIT_SCHEMA_VERSION
    assert event.event_type == "structured_analysis_failed"
    assert event.status == "failure"


def test_failure_event_records_error_type_class_name() -> None:
    assert make_failure_event().error_type == "RuntimeError"


def test_failure_event_records_recovery_action_and_retryable() -> None:
    event = make_failure_event()

    assert event.recovery_action == "abort"
    assert event.retryable is False


def test_failure_event_does_not_record_error_message() -> None:
    assert_no_secret(asdict(make_failure_event()))


def test_append_audit_event_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())

    assert path.exists()


def test_append_audit_event_writes_one_event_per_line(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_append_audit_event_appends_two_events(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())
    append_audit_event(path=path, event=make_failure_event())

    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_audit_event_lines_are_json(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())
    append_audit_event(path=path, event=make_failure_event())

    for line in path.read_text(encoding="utf-8").splitlines():
        assert json.loads(line)["schema_version"] == AUDIT_SCHEMA_VERSION


def test_append_audit_event_ends_with_newline(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())

    assert path.read_text(encoding="utf-8").endswith("\n")


def test_append_audit_event_preserves_unicode(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"

    append_audit_event(path=path, event=make_success_event())

    assert "structured_analysis_completed" in path.read_text(encoding="utf-8")


def test_append_audit_event_converts_oserror_to_audit_log_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def raise_oserror(self: Path, *args: object, **kwargs: object) -> object:
        raise OSError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(Path, "open", raise_oserror)

    with pytest.raises(AuditLogError) as exc_info:
        append_audit_event(path=tmp_path / "audit.jsonl", event=make_success_event())

    assert str(exc_info.value) == "Failed to write the structured analysis audit log."
    assert "PRIVATE-ERROR-MESSAGE" not in str(exc_info.value)
