from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.audit_report import (
    AuditReport,
    ModelAuditStats,
    ParsedAuditEvents,
    ParsedFailureEvent,
    ParsedSuccessEvent,
    build_audit_report,
    format_audit_report,
    read_audit_events,
)
from app.exceptions import (
    AuditLogParseError,
    AuditLogReadError,
    InvalidAuditEventError,
    UnsupportedAuditSchemaError,
)
from app.observability import AUDIT_SCHEMA_VERSION

SECRET_VALUES = (
    "sk-test-do-not-log",
    "PRIVATE-SUMMARY",
    "PRIVATE-KEYWORD",
    "PRIVATE-REVIEW-REASON",
    "PRIVATE-ERROR-MESSAGE",
)


def success_event(
    *,
    model: str = "gpt-test",
    attempts: int = 1,
    correction_attempted: bool = False,
    total_tokens: int | None = 30,
    elapsed_seconds: float = 0.5,
) -> dict[str, object]:
    recorded_usage = None
    if total_tokens is not None:
        recorded_usage = {
            "input_tokens": 10,
            "cached_input_tokens": 1,
            "output_tokens": 20,
            "reasoning_tokens": 2,
            "total_tokens": total_tokens,
        }
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_completed",
        "timestamp_utc": "2026-08-02T00:00:00+00:00",
        "status": "success",
        "model": model,
        "attempts": attempts,
        "correction_attempted": correction_attempted,
        "recorded_usage": recorded_usage,
        "total_elapsed_seconds": elapsed_seconds,
        "response_ids": ["resp-private"],
        "final_response_id": "resp-private-final",
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
    error_type: str = "RuntimeError",
    recovery_action: str = "abort",
    retryable: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_failed",
        "timestamp_utc": "2026-08-02T00:00:00+00:00",
        "status": "failure",
        "model": model,
        "error_type": error_type,
        "recovery_action": recovery_action,
        "retryable": retryable,
        "budget": {
            "max_attempts": 2,
            "max_recorded_tokens": 2000,
            "max_elapsed_seconds": 30.0,
        },
    }


def write_events(path: Path, *events: dict[str, object]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )


def read_one_error(path: Path) -> str:
    try:
        read_audit_events(path)
    except Exception as error:  # noqa: BLE001
        return str(error)
    raise AssertionError("Expected read_audit_events to fail")


def assert_no_secret(value: object) -> None:
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    for secret in SECRET_VALUES:
        assert secret not in encoded


def test_read_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")

    assert read_audit_events(path) == ParsedAuditEvents(successes=(), failures=())


def test_read_ignores_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("  \n\n", encoding="utf-8")

    assert read_audit_events(path).successes == ()


def test_read_success_event(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event())

    events = read_audit_events(path)

    assert events.successes == (ParsedSuccessEvent("gpt-test", 1, False, 30, 0.5),)
    assert events.failures == ()


def test_read_failure_event(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, failure_event())

    events = read_audit_events(path)

    assert events.failures == (ParsedFailureEvent("gpt-test", "RuntimeError", "abort", False),)


def test_read_multiple_success_and_failure_events(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(), failure_event(), success_event(model="gpt-other"))

    events = read_audit_events(path)

    assert len(events.successes) == 2
    assert len(events.failures) == 1


def test_read_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("{PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")

    with pytest.raises(AuditLogParseError):
        read_audit_events(path)
    assert_no_secret(read_one_error(path))


def test_read_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    event["schema_version"] = 999
    write_events(path, event)

    with pytest.raises(UnsupportedAuditSchemaError):
        read_audit_events(path)


def test_read_rejects_non_object_payload(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_missing_common_field(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    del event["model"]
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_unknown_event_type(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    event["event_type"] = "unknown"
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_event_type_status_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    event["status"] = "failure"
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_empty_model(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(model=""))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_bool_attempts(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    event["attempts"] = True
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_zero_attempts(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(attempts=0))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_negative_latency(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(elapsed_seconds=-0.1))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_allows_recorded_usage_none(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(total_tokens=None))

    assert read_audit_events(path).successes[0].recorded_total_tokens is None


def test_read_rejects_recorded_usage_missing_total_tokens(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    assert isinstance(event["recorded_usage"], dict)
    del event["recorded_usage"]["total_tokens"]
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_bool_total_tokens(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    assert isinstance(event["recorded_usage"], dict)
    event["recorded_usage"]["total_tokens"] = False
    write_events(path, event)

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_negative_total_tokens(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(total_tokens=-1))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_empty_failure_error_type(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, failure_event(error_type=""))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_non_bool_failure_retryable(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, failure_event(retryable="false"))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_missing_file_raises_read_error(tmp_path: Path) -> None:
    with pytest.raises(AuditLogReadError):
        read_audit_events(tmp_path / "missing.jsonl")


def test_read_oserror_raises_read_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def raise_oserror(self: Path, *args: object, **kwargs: object) -> object:
        raise OSError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(Path, "open", raise_oserror)

    with pytest.raises(AuditLogReadError) as exc_info:
        read_audit_events(tmp_path / "audit.jsonl")
    assert "PRIVATE-ERROR-MESSAGE" not in str(exc_info.value)


def test_read_errors_do_not_include_raw_sensitive_line(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("PRIVATE-ERROR-MESSAGE\n", encoding="utf-8")

    assert_no_secret(read_one_error(path))


def make_report_events() -> ParsedAuditEvents:
    return ParsedAuditEvents(
        successes=(
            ParsedSuccessEvent("gpt-b", 1, False, 20, 0.2),
            ParsedSuccessEvent("gpt-a", 2, True, 40, 0.4),
            ParsedSuccessEvent("gpt-a", 1, False, None, 1.0),
        ),
        failures=(
            ParsedFailureEvent("gpt-b", "ZError", "abort", False),
            ParsedFailureEvent("gpt-b", "AError", "retry_later", True),
            ParsedFailureEvent("gpt-a", "AError", "abort", False),
        ),
    )


def test_report_counts_total_success_and_failure_events() -> None:
    report = build_audit_report(make_report_events())

    assert report.total_events == 6
    assert report.success_count == 3
    assert report.failure_count == 3


def test_report_success_rate() -> None:
    assert build_audit_report(make_report_events()).success_rate == 0.5


def test_report_correction_count_and_rate() -> None:
    report = build_audit_report(make_report_events())

    assert report.corrected_success_count == 1
    assert report.correction_rate == pytest.approx(1 / 3)


def test_report_average_attempts() -> None:
    assert build_audit_report(make_report_events()).average_attempts == pytest.approx(4 / 3)


def test_report_usage_event_count() -> None:
    assert build_audit_report(make_report_events()).usage_event_count == 2


def test_report_token_sum_and_average() -> None:
    report = build_audit_report(make_report_events())

    assert report.recorded_total_tokens == 60
    assert report.average_recorded_tokens == 30.0


def test_report_latency_average_and_max() -> None:
    report = build_audit_report(make_report_events())

    assert report.average_elapsed_seconds == pytest.approx(1.6 / 3)
    assert report.max_elapsed_seconds == 1.0


def test_report_retryable_and_non_retryable_failures() -> None:
    report = build_audit_report(make_report_events())

    assert report.retryable_failure_count == 1
    assert report.non_retryable_failure_count == 2


def test_report_errors_by_type_are_counted_and_sorted() -> None:
    assert build_audit_report(make_report_events()).errors_by_type == (
        ("AError", 2),
        ("ZError", 1),
    )


def test_report_recovery_actions_are_counted_and_sorted() -> None:
    assert build_audit_report(make_report_events()).recovery_actions == (
        ("abort", 2),
        ("retry_later", 1),
    )


def test_report_model_stats() -> None:
    report = build_audit_report(make_report_events())

    assert report.models[0] == ModelAuditStats("gpt-a", 3, 2, 1, 2 / 3, 40, 0.7)


def test_report_models_are_sorted_by_name() -> None:
    assert [model.model for model in build_audit_report(make_report_events()).models] == [
        "gpt-a",
        "gpt-b",
    ]


def test_report_empty_events_return_zero_values_and_empty_tuples() -> None:
    report = build_audit_report(ParsedAuditEvents(successes=(), failures=()))

    assert report == AuditReport(
        total_events=0,
        success_count=0,
        failure_count=0,
        success_rate=0.0,
        corrected_success_count=0,
        correction_rate=0.0,
        average_attempts=0.0,
        usage_event_count=0,
        recorded_total_tokens=0,
        average_recorded_tokens=0.0,
        average_elapsed_seconds=0.0,
        max_elapsed_seconds=0.0,
        retryable_failure_count=0,
        non_retryable_failure_count=0,
        errors_by_type=(),
        recovery_actions=(),
        models=(),
    )


def test_report_usage_none_is_excluded_from_token_average() -> None:
    report = build_audit_report(
        ParsedAuditEvents(
            successes=(
                ParsedSuccessEvent("gpt", 1, False, None, 0.1),
                ParsedSuccessEvent("gpt", 1, False, 10, 0.1),
            ),
            failures=(),
        )
    )

    assert report.usage_event_count == 1
    assert report.average_recorded_tokens == 10.0


def test_formatter_includes_all_sections() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    for section in (
        "Structured Analysis Audit Report",
        "Summary",
        "Correction",
        "Recorded Usage",
        "Latency",
        "Failures",
        "Errors By Type",
        "Recovery Actions",
        "Models",
    ):
        assert section in output


def test_formatter_formats_percent_with_two_decimals() -> None:
    assert "Success Rate: 50.00%" in format_audit_report(
        build_audit_report(make_report_events())
    )


def test_formatter_formats_averages_with_three_decimals() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    assert "Average Attempts: 1.333" in output


def test_formatter_prints_none_for_empty_aggregates() -> None:
    output = format_audit_report(build_audit_report(ParsedAuditEvents((), ())))

    assert "Errors By Type\n  None" in output
    assert "Recovery Actions\n  None" in output
    assert "Models\n  None" in output


def test_formatter_does_not_output_response_id() -> None:
    path_event = success_event()
    assert "resp-private" not in format_audit_report(
        build_audit_report(
            ParsedAuditEvents(
                successes=(ParsedSuccessEvent("gpt", 1, False, 1, 0.1),),
                failures=(),
            )
        )
    )
    assert "resp-private" in json.dumps(path_event)


def test_formatter_does_not_output_request_id() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    assert "req-private" not in output


def test_formatter_does_not_output_private_summary() -> None:
    assert "PRIVATE-SUMMARY" not in format_audit_report(build_audit_report(make_report_events()))


def test_formatter_does_not_output_private_keyword() -> None:
    assert "PRIVATE-KEYWORD" not in format_audit_report(build_audit_report(make_report_events()))


def test_formatter_does_not_output_private_review_reason() -> None:
    assert "PRIVATE-REVIEW-REASON" not in format_audit_report(
        build_audit_report(make_report_events())
    )


def test_formatter_does_not_output_private_error_message() -> None:
    assert "PRIVATE-ERROR-MESSAGE" not in format_audit_report(
        build_audit_report(make_report_events())
    )


def test_parsed_events_do_not_preserve_sensitive_fields(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    event = success_event()
    event["summary"] = "PRIVATE-SUMMARY"
    event["keywords"] = ["PRIVATE-KEYWORD"]
    event["review_reason"] = "PRIVATE-REVIEW-REASON"
    write_events(path, event)

    assert_no_secret(asdict(read_audit_events(path)))
