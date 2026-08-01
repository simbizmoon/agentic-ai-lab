from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.audit_report import (
    AUDIT_REPORT_SCHEMA_VERSION,
    AuditErrorCountPayload,
    AuditModelStatsPayload,
    AuditRecoveryActionCountPayload,
    AuditReport,
    AuditReportCorrectionPayload,
    AuditReportFailuresPayload,
    AuditReportFilter,
    AuditReportFilterPayload,
    AuditReportFormat,
    AuditReportLatencyPayload,
    AuditReportPayload,
    AuditReportSummaryPayload,
    AuditReportUsagePayload,
    AuditStatusFilter,
    ModelAuditStats,
    ParsedAuditEvents,
    ParsedFailureEvent,
    ParsedSuccessEvent,
    build_audit_report,
    build_audit_report_payload,
    filter_audit_events,
    format_audit_report,
    format_audit_report_json,
    read_audit_events,
    render_audit_report,
    validate_audit_report_json,
)
from app.exceptions import (
    AuditLogParseError,
    AuditLogReadError,
    AuditReportValidationError,
    InvalidAuditEventError,
    UnsupportedAuditSchemaError,
)
from app.observability import AUDIT_SCHEMA_VERSION
from app.recovery import RecoveryAction

SECRET_VALUES = (
    "sk-test-do-not-log",
    "PRIVATE-SUMMARY",
    "PRIVATE-KEYWORD",
    "PRIVATE-REVIEW-REASON",
    "PRIVATE-ERROR-MESSAGE",
    "PRIVATE-TIMESTAMP",
)
BASE_TIME = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)


def success_event(
    *,
    model: str = "gpt-test",
    timestamp_utc: object = "2026-08-02T00:00:00+00:00",
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
        "timestamp_utc": timestamp_utc,
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
    timestamp_utc: object = "2026-08-02T00:00:00+00:00",
    error_type: str = "RuntimeError",
    recovery_action: str = "abort",
    retryable: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_type": "structured_analysis_failed",
        "timestamp_utc": timestamp_utc,
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


def parsed_success(
    model: str = "gpt-test",
    timestamp_utc: datetime = BASE_TIME,
    attempts: int = 1,
    correction_attempted: bool = False,
    recorded_total_tokens: int | None = 30,
    total_elapsed_seconds: float = 0.5,
) -> ParsedSuccessEvent:
    return ParsedSuccessEvent(
        model=model,
        timestamp_utc=timestamp_utc,
        attempts=attempts,
        correction_attempted=correction_attempted,
        recorded_total_tokens=recorded_total_tokens,
        total_elapsed_seconds=total_elapsed_seconds,
    )


def parsed_failure(
    model: str = "gpt-test",
    timestamp_utc: datetime = BASE_TIME,
    error_type: str = "RuntimeError",
    recovery_action: str = "abort",
    retryable: bool = False,
) -> ParsedFailureEvent:
    return ParsedFailureEvent(
        model=model,
        timestamp_utc=timestamp_utc,
        error_type=error_type,
        recovery_action=recovery_action,
        retryable=retryable,
    )


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

    assert events.successes == (parsed_success(),)
    assert events.failures == ()


def test_read_failure_event(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, failure_event())

    events = read_audit_events(path)

    assert events.failures == (parsed_failure(),)


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


def test_read_parses_utc_offset_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="2026-08-02T00:00:00+00:00"))

    assert read_audit_events(path).successes[0].timestamp_utc == BASE_TIME


def test_read_parses_z_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="2026-08-02T00:00:00Z"))

    assert read_audit_events(path).successes[0].timestamp_utc == BASE_TIME


def test_read_normalizes_non_utc_timestamp_to_utc(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="2026-08-02T09:00:00+09:00"))

    assert read_audit_events(path).successes[0].timestamp_utc == BASE_TIME


def test_read_rejects_invalid_iso_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="not-a-timestamp"))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_naive_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="2026-08-02T00:00:00"))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_read_rejects_non_string_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc=123))

    with pytest.raises(InvalidAuditEventError):
        read_audit_events(path)


def test_timestamp_error_omits_raw_sensitive_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_events(path, success_event(timestamp_utc="PRIVATE-TIMESTAMP"))

    assert_no_secret(read_one_error(path))


def make_report_events() -> ParsedAuditEvents:
    return ParsedAuditEvents(
        successes=(
            parsed_success("gpt-b", BASE_TIME, 1, False, 20, 0.2),
            parsed_success("gpt-a", BASE_TIME + timedelta(minutes=1), 2, True, 40, 0.4),
            parsed_success("gpt-a", BASE_TIME + timedelta(minutes=2), 1, False, None, 1.0),
        ),
        failures=(
            parsed_failure("gpt-b", BASE_TIME, "ZError", "abort", False),
            parsed_failure("gpt-b", BASE_TIME + timedelta(minutes=1), "AError", "retry_later", True),
            parsed_failure("gpt-a", BASE_TIME + timedelta(minutes=2), "AError", "abort", False),
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
                parsed_success(recorded_total_tokens=None),
                parsed_success(recorded_total_tokens=10),
            ),
            failures=(),
        )
    )

    assert report.usage_event_count == 1
    assert report.average_recorded_tokens == 10.0


def test_audit_report_filter_defaults() -> None:
    report_filter = AuditReportFilter()

    assert report_filter.since is None
    assert report_filter.until is None
    assert report_filter.model is None
    assert report_filter.status is AuditStatusFilter.ALL


def test_audit_report_filter_accepts_since() -> None:
    assert AuditReportFilter(since=BASE_TIME).since == BASE_TIME


def test_audit_report_filter_accepts_until() -> None:
    assert AuditReportFilter(until=BASE_TIME).until == BASE_TIME


def test_audit_report_filter_accepts_model() -> None:
    assert AuditReportFilter(model="gpt-test").model == "gpt-test"


def test_audit_status_filter_values() -> None:
    assert AuditStatusFilter.ALL.value == "all"
    assert AuditStatusFilter.SUCCESS.value == "success"
    assert AuditStatusFilter.FAILURE.value == "failure"


def test_audit_report_filter_rejects_naive_since() -> None:
    with pytest.raises(ValueError, match="since"):
        AuditReportFilter(since=BASE_TIME.replace(tzinfo=None))


def test_audit_report_filter_rejects_naive_until() -> None:
    with pytest.raises(ValueError, match="until"):
        AuditReportFilter(until=BASE_TIME.replace(tzinfo=None))


def test_audit_report_filter_rejects_same_since_and_until() -> None:
    with pytest.raises(ValueError, match="since"):
        AuditReportFilter(since=BASE_TIME, until=BASE_TIME)


def test_audit_report_filter_rejects_since_after_until() -> None:
    with pytest.raises(ValueError, match="since"):
        AuditReportFilter(since=BASE_TIME + timedelta(seconds=1), until=BASE_TIME)


def test_audit_report_filter_rejects_empty_model() -> None:
    with pytest.raises(ValueError, match="model"):
        AuditReportFilter(model="")


def test_audit_report_filter_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model"):
        AuditReportFilter(model="   ")


def test_audit_report_filter_rejects_surrounding_model_whitespace() -> None:
    with pytest.raises(ValueError, match="model"):
        AuditReportFilter(model=" gpt-test ")


def test_audit_report_filter_is_frozen() -> None:
    report_filter = AuditReportFilter()

    with pytest.raises(FrozenInstanceError):
        report_filter.model = "gpt-test"


def make_filter_events() -> ParsedAuditEvents:
    return ParsedAuditEvents(
        successes=(
            parsed_success("gpt-a", BASE_TIME),
            parsed_success("gpt-A", BASE_TIME + timedelta(minutes=1)),
            parsed_success("gpt-b", BASE_TIME + timedelta(minutes=2)),
        ),
        failures=(
            parsed_failure("gpt-a", BASE_TIME + timedelta(minutes=3)),
            parsed_failure("gpt-b", BASE_TIME + timedelta(minutes=4)),
        ),
    )


def test_filter_default_keeps_all_events() -> None:
    events = make_filter_events()

    assert filter_audit_events(events=events, report_filter=AuditReportFilter()) == events


def test_filter_since_includes_boundary() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(since=BASE_TIME),
    )

    assert len(filtered.successes) == 3
    assert len(filtered.failures) == 2


def test_filter_since_excludes_earlier_events() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(since=BASE_TIME + timedelta(minutes=2)),
    )

    assert [event.model for event in filtered.successes] == ["gpt-b"]
    assert len(filtered.failures) == 2


def test_filter_until_excludes_boundary() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(until=BASE_TIME + timedelta(minutes=2)),
    )

    assert [event.model for event in filtered.successes] == ["gpt-a", "gpt-A"]


def test_filter_until_includes_earlier_events() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(until=BASE_TIME + timedelta(minutes=1)),
    )

    assert filtered.successes == (parsed_success("gpt-a", BASE_TIME),)


def test_filter_compares_equivalent_times_with_different_offsets() -> None:
    plus_nine = datetime(2026, 8, 2, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(since=plus_nine),
    )

    assert len(filtered.successes) == 3


def test_filter_model_exact_match() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(model="gpt-a"),
    )

    assert len(filtered.successes) == 1
    assert len(filtered.failures) == 1


def test_filter_model_is_case_sensitive() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(model="gpt-A"),
    )

    assert filtered.successes == (parsed_success("gpt-A", BASE_TIME + timedelta(minutes=1)),)
    assert filtered.failures == ()


def test_filter_status_success() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(status=AuditStatusFilter.SUCCESS),
    )

    assert len(filtered.successes) == 3
    assert filtered.failures == ()


def test_filter_status_failure() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(status=AuditStatusFilter.FAILURE),
    )

    assert filtered.successes == ()
    assert len(filtered.failures) == 2


def test_filter_status_all() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(status=AuditStatusFilter.ALL),
    )

    assert len(filtered.successes) == 3
    assert len(filtered.failures) == 2


def test_filter_combines_period_model_and_status_with_and() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(
            since=BASE_TIME + timedelta(minutes=2),
            until=BASE_TIME + timedelta(minutes=5),
            model="gpt-b",
            status=AuditStatusFilter.FAILURE,
        ),
    )

    assert filtered.successes == ()
    assert filtered.failures == (
        parsed_failure("gpt-b", BASE_TIME + timedelta(minutes=4)),
    )


def test_filter_empty_result_is_valid() -> None:
    filtered = filter_audit_events(
        events=make_filter_events(),
        report_filter=AuditReportFilter(model="missing-model"),
    )

    assert filtered == ParsedAuditEvents(successes=(), failures=())


def test_filter_does_not_mutate_original_events() -> None:
    events = make_filter_events()
    before = events

    filter_audit_events(
        events=events,
        report_filter=AuditReportFilter(model="missing-model"),
    )

    assert events == before


def test_formatter_includes_all_sections() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    for section in (
        "Structured Analysis Audit Report",
        "Filters",
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


def test_formatter_includes_filters_section() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    assert "Filters" in output


def test_formatter_default_filter_outputs_all() -> None:
    output = format_audit_report(build_audit_report(make_report_events()))

    assert "Since: all" in output
    assert "Until: all" in output
    assert "Model: all" in output
    assert "Status: all" in output


def test_formatter_outputs_utc_iso_datetimes() -> None:
    output = format_audit_report(
        build_audit_report(make_report_events()),
        report_filter=AuditReportFilter(
            since=BASE_TIME,
            until=BASE_TIME + timedelta(hours=1),
        ),
    )

    assert "Since: 2026-08-02T00:00:00+00:00" in output
    assert "Until: 2026-08-02T01:00:00+00:00" in output


def test_formatter_outputs_model_filter() -> None:
    output = format_audit_report(
        build_audit_report(make_report_events()),
        report_filter=AuditReportFilter(model="gpt-a"),
    )

    assert "Model: gpt-a" in output


def test_formatter_outputs_status_filter() -> None:
    output = format_audit_report(
        build_audit_report(make_report_events()),
        report_filter=AuditReportFilter(status=AuditStatusFilter.FAILURE),
    )

    assert "Status: failure" in output


def test_formatter_keeps_existing_sections_with_filters() -> None:
    output = format_audit_report(
        build_audit_report(make_report_events()),
        report_filter=AuditReportFilter(status=AuditStatusFilter.SUCCESS),
    )

    assert "Summary" in output
    assert "Recovery Actions" in output
    assert "Models" in output


def test_formatter_does_not_output_response_id() -> None:
    path_event = success_event()
    assert "resp-private" not in format_audit_report(
        build_audit_report(
            ParsedAuditEvents(
                successes=(parsed_success(recorded_total_tokens=1, total_elapsed_seconds=0.1),),
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



def make_payload_report() -> AuditReport:
    return build_audit_report(make_report_events())


def make_payload_filter() -> AuditReportFilter:
    return AuditReportFilter(
        since=BASE_TIME,
        until=BASE_TIME + timedelta(hours=1),
        model="gpt-a",
        status=AuditStatusFilter.SUCCESS,
    )


def payload_dict(
    report_filter: AuditReportFilter | None = None,
) -> dict[str, object]:
    return build_audit_report_payload(
        report=make_payload_report(),
        report_filter=report_filter,
    ).model_dump(mode="json")


def payload_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if isinstance(key, str):
                keys.add(key)
            keys.update(payload_keys(nested_value))
    elif isinstance(value, list):
        for item in value:
            keys.update(payload_keys(item))
    return keys


def test_audit_report_format_values() -> None:
    assert AuditReportFormat.TEXT.value == "text"
    assert AuditReportFormat.JSON.value == "json"


def test_audit_report_format_is_str_enum() -> None:
    assert isinstance(AuditReportFormat.TEXT, str)


def test_payload_schema_version() -> None:
    assert payload_dict()["schema_version"] == AUDIT_REPORT_SCHEMA_VERSION


def test_payload_report_type() -> None:
    assert payload_dict()["report_type"] == "structured_analysis_audit_report"


def test_payload_top_level_keys() -> None:
    payload = payload_dict()

    assert set(payload) == {
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
    }


def test_payload_top_level_key_order() -> None:
    payload = payload_dict()

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


def test_payload_default_filter_uses_none_and_all_status() -> None:
    filters = payload_dict()["filters"]

    assert filters == {"since": None, "until": None, "model": None, "status": "all"}


def test_payload_filter_timestamps_are_utc_iso() -> None:
    filters = payload_dict(make_payload_filter())["filters"]

    assert filters["since"] == "2026-08-02T00:00:00+00:00"
    assert filters["until"] == "2026-08-02T01:00:00+00:00"


def test_payload_filter_model_and_status() -> None:
    filters = payload_dict(make_payload_filter())["filters"]

    assert filters["model"] == "gpt-a"
    assert filters["status"] == "success"


def test_payload_summary_values() -> None:
    summary = payload_dict()["summary"]

    assert summary == {
        "total_events": 6,
        "success_count": 3,
        "failure_count": 3,
        "success_rate": 0.5,
    }


def test_payload_correction_values() -> None:
    correction = payload_dict()["correction"]

    assert correction["corrected_success_count"] == 1
    assert correction["correction_rate"] == pytest.approx(1 / 3)
    assert correction["average_attempts"] == pytest.approx(4 / 3)


def test_payload_recorded_usage_values() -> None:
    recorded_usage = payload_dict()["recorded_usage"]

    assert recorded_usage == {
        "usage_event_count": 2,
        "total_tokens": 60,
        "average_tokens": 30.0,
    }


def test_payload_latency_values() -> None:
    latency = payload_dict()["latency"]

    assert latency["average_success_elapsed_seconds"] == pytest.approx(1.6 / 3)
    assert latency["maximum_success_elapsed_seconds"] == 1.0


def test_payload_failure_values() -> None:
    failures = payload_dict()["failures"]

    assert failures == {"retryable_count": 1, "non_retryable_count": 2}


def test_payload_errors_by_type_structure_and_order() -> None:
    assert payload_dict()["errors_by_type"] == [
        {"error_type": "AError", "count": 2},
        {"error_type": "ZError", "count": 1},
    ]


def test_payload_recovery_actions_structure_and_order() -> None:
    assert payload_dict()["recovery_actions"] == [
        {"action": "abort", "count": 2},
        {"action": "retry_later", "count": 1},
    ]


def test_payload_models_structure_and_order() -> None:
    models = payload_dict()["models"]

    assert models[0] == {
        "model": "gpt-a",
        "total_events": 3,
        "success_count": 2,
        "failure_count": 1,
        "success_rate": 2 / 3,
        "recorded_total_tokens": 40,
        "average_success_elapsed_seconds": 0.7,
    }
    assert models[1]["model"] == "gpt-b"


def test_payload_ratios_are_float() -> None:
    payload = payload_dict()

    assert isinstance(payload["summary"]["success_rate"], float)
    assert isinstance(payload["correction"]["correction_rate"], float)


def test_payload_tokens_are_int() -> None:
    payload = payload_dict()

    assert isinstance(payload["recorded_usage"]["total_tokens"], int)
    assert isinstance(payload["models"][0]["recorded_total_tokens"], int)


def test_empty_report_payload() -> None:
    payload = build_audit_report_payload(
        report=build_audit_report(ParsedAuditEvents((), ()))
    ).model_dump(mode="json")

    assert payload["summary"]["total_events"] == 0
    assert payload["errors_by_type"] == []
    assert payload["models"] == []


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "response_id",
        "request_id",
        "user_input",
        "prompt",
        "instructions",
        "topic",
        "keyword",
        "review_reason",
        "error_message",
    ],
)
def test_payload_omits_sensitive_keys(forbidden_key: str) -> None:
    payload = payload_dict()

    assert forbidden_key not in payload_keys(payload)


@pytest.mark.parametrize(
    "secret",
    [
        "sk-test-do-not-log",
        "PRIVATE-SUMMARY",
        "PRIVATE-KEYWORD",
        "PRIVATE-REVIEW-REASON",
        "PRIVATE-ERROR-MESSAGE",
    ],
)
def test_payload_omits_sensitive_values(secret: str) -> None:
    payload = payload_dict()

    assert secret not in json.dumps(payload, ensure_ascii=False)


def test_json_formatter_output_is_loadable() -> None:
    output = format_audit_report_json(make_payload_report())

    assert json.loads(output)["report_type"] == "structured_analysis_audit_report"


def test_json_formatter_schema_version() -> None:
    payload = json.loads(format_audit_report_json(make_payload_report()))

    assert payload["schema_version"] == AUDIT_REPORT_SCHEMA_VERSION


def test_json_formatter_preserves_unicode() -> None:
    report = build_audit_report(
        ParsedAuditEvents(
            successes=(parsed_success(model="한국어-모델"),),
            failures=(),
        )
    )

    assert "한국어-모델" in format_audit_report_json(report)


def test_json_formatter_uses_two_space_indent() -> None:
    output = format_audit_report_json(make_payload_report())

    assert "\n  \"schema_version\"" in output


def test_json_formatter_outputs_only_json() -> None:
    output = format_audit_report_json(make_payload_report())

    assert output.startswith("{")
    assert "Structured Analysis Audit Report" not in output


def test_json_formatter_does_not_mutate_report() -> None:
    report = make_payload_report()
    before = report

    format_audit_report_json(report)

    assert report == before


def test_json_formatter_does_not_mutate_filter() -> None:
    report_filter = make_payload_filter()
    before = report_filter

    format_audit_report_json(make_payload_report(), report_filter=report_filter)

    assert report_filter == before


def test_render_text_matches_text_formatter() -> None:
    report = make_payload_report()
    report_filter = make_payload_filter()

    assert render_audit_report(
        report=report,
        report_filter=report_filter,
        report_format=AuditReportFormat.TEXT,
    ) == format_audit_report(report, report_filter=report_filter)


def test_render_json_matches_json_formatter() -> None:
    report = make_payload_report()
    report_filter = make_payload_filter()

    assert render_audit_report(
        report=report,
        report_filter=report_filter,
        report_format=AuditReportFormat.JSON,
    ) == format_audit_report_json(report, report_filter=report_filter)


def test_render_rejects_unsupported_format() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        render_audit_report(
            report=make_payload_report(),
            report_filter=AuditReportFilter(),
            report_format=cast(AuditReportFormat, "xml"),
        )


def test_text_and_json_total_events_match() -> None:
    report = make_payload_report()
    text = format_audit_report(report)
    payload = build_audit_report_payload(report=report).model_dump(mode="json")

    assert f"Total Events: {payload['summary']['total_events']}" in text


def test_text_and_json_success_failure_counts_match() -> None:
    report = make_payload_report()
    text = format_audit_report(report)
    payload = build_audit_report_payload(report=report).model_dump(mode="json")

    assert f"Successes: {payload['summary']['success_count']}" in text
    assert f"Failures: {payload['summary']['failure_count']}" in text


def test_text_percentage_matches_json_ratio() -> None:
    report = make_payload_report()
    text = format_audit_report(report)
    payload = build_audit_report_payload(report=report).model_dump(mode="json")
    expected_percent = f"{payload['summary']['success_rate'] * 100:.2f}%"

    assert f"Success Rate: {expected_percent}" in text



def valid_payload_model() -> AuditReportPayload:
    return build_audit_report_payload(report=make_payload_report())


def valid_payload_data() -> dict[str, object]:
    return valid_payload_model().model_dump(mode="json")


def test_payload_model_rejects_extra_field() -> None:
    data = valid_payload_data()
    data["extra_field"] = "not allowed"

    with pytest.raises(ValidationError):
        AuditReportPayload.model_validate_json(json.dumps(data))


def test_payload_model_rejects_string_int() -> None:
    with pytest.raises(ValidationError):
        AuditReportSummaryPayload(
            total_events="1",
            success_count=1,
            failure_count=0,
            success_rate=1.0,
        )


def test_payload_model_rejects_string_float() -> None:
    with pytest.raises(ValidationError):
        AuditReportSummaryPayload(
            total_events=1,
            success_count=1,
            failure_count=0,
            success_rate="1.0",
        )


def test_payload_model_rejects_string_enum_value_in_python_mode() -> None:
    with pytest.raises(ValidationError):
        AuditReportFilterPayload(
            since=None,
            until=None,
            model=None,
            status="all",
        )


def test_summary_payload_accepts_valid_values() -> None:
    payload = AuditReportSummaryPayload(
        total_events=2,
        success_count=1,
        failure_count=1,
        success_rate=0.5,
    )

    assert payload.success_rate == 0.5


def test_summary_payload_rejects_count_mismatch() -> None:
    with pytest.raises(ValidationError):
        AuditReportSummaryPayload(
            total_events=3,
            success_count=1,
            failure_count=1,
            success_rate=1 / 3,
        )


def test_summary_payload_rejects_success_rate_mismatch() -> None:
    with pytest.raises(ValidationError):
        AuditReportSummaryPayload(
            total_events=2,
            success_count=1,
            failure_count=1,
            success_rate=0.9,
        )


def test_summary_payload_allows_zero_events_and_zero_rate() -> None:
    payload = AuditReportSummaryPayload(
        total_events=0,
        success_count=0,
        failure_count=0,
        success_rate=0.0,
    )

    assert payload.success_rate == 0.0


def test_summary_payload_rejects_rate_out_of_range() -> None:
    with pytest.raises(ValidationError):
        AuditReportSummaryPayload(
            total_events=1,
            success_count=1,
            failure_count=0,
            success_rate=1.1,
        )


def test_correction_payload_accepts_valid_values() -> None:
    payload = AuditReportCorrectionPayload(
        corrected_success_count=1,
        correction_rate=0.5,
        average_attempts=1.5,
    )

    assert payload.corrected_success_count == 1


def test_correction_payload_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        AuditReportCorrectionPayload(
            corrected_success_count=-1,
            correction_rate=0.0,
            average_attempts=0.0,
        )


def test_correction_payload_rejects_rate_out_of_range() -> None:
    with pytest.raises(ValidationError):
        AuditReportCorrectionPayload(
            corrected_success_count=0,
            correction_rate=-0.1,
            average_attempts=0.0,
        )


def test_usage_payload_accepts_valid_values() -> None:
    payload = AuditReportUsagePayload(
        usage_event_count=2,
        total_tokens=10,
        average_tokens=5.0,
    )

    assert payload.average_tokens == 5.0


def test_usage_payload_allows_zero_values() -> None:
    payload = AuditReportUsagePayload(
        usage_event_count=0,
        total_tokens=0,
        average_tokens=0.0,
    )

    assert payload.total_tokens == 0


def test_usage_payload_rejects_average_mismatch() -> None:
    with pytest.raises(ValidationError):
        AuditReportUsagePayload(
            usage_event_count=2,
            total_tokens=10,
            average_tokens=6.0,
        )


def test_usage_payload_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        AuditReportUsagePayload(
            usage_event_count=1,
            total_tokens=-1,
            average_tokens=0.0,
        )


def test_latency_payload_accepts_valid_values() -> None:
    payload = AuditReportLatencyPayload(
        average_success_elapsed_seconds=0.5,
        maximum_success_elapsed_seconds=1.0,
    )

    assert payload.maximum_success_elapsed_seconds == 1.0


def test_latency_payload_rejects_average_greater_than_maximum() -> None:
    with pytest.raises(ValidationError):
        AuditReportLatencyPayload(
            average_success_elapsed_seconds=2.0,
            maximum_success_elapsed_seconds=1.0,
        )


def test_latency_payload_rejects_negative_value() -> None:
    with pytest.raises(ValidationError):
        AuditReportLatencyPayload(
            average_success_elapsed_seconds=-1.0,
            maximum_success_elapsed_seconds=1.0,
        )


def test_model_stats_payload_accepts_valid_values() -> None:
    payload = AuditModelStatsPayload(
        model="gpt-test",
        total_events=2,
        success_count=1,
        failure_count=1,
        success_rate=0.5,
        recorded_total_tokens=10,
        average_success_elapsed_seconds=0.5,
    )

    assert payload.model == "gpt-test"


def test_model_stats_payload_rejects_count_mismatch() -> None:
    with pytest.raises(ValidationError):
        AuditModelStatsPayload(
            model="gpt-test",
            total_events=3,
            success_count=1,
            failure_count=1,
            success_rate=1 / 3,
            recorded_total_tokens=10,
            average_success_elapsed_seconds=0.5,
        )


def test_model_stats_payload_rejects_success_rate_mismatch() -> None:
    with pytest.raises(ValidationError):
        AuditModelStatsPayload(
            model="gpt-test",
            total_events=2,
            success_count=1,
            failure_count=1,
            success_rate=0.9,
            recorded_total_tokens=10,
            average_success_elapsed_seconds=0.5,
        )


def test_model_stats_payload_rejects_surrounding_whitespace() -> None:
    with pytest.raises(ValidationError):
        AuditModelStatsPayload(
            model=" gpt-test ",
            total_events=1,
            success_count=1,
            failure_count=0,
            success_rate=1.0,
            recorded_total_tokens=10,
            average_success_elapsed_seconds=0.5,
        )


def test_failures_payload_accepts_valid_values() -> None:
    payload = AuditReportFailuresPayload(retryable_count=1, non_retryable_count=2)

    assert payload.retryable_count == 1


def test_error_count_payload_rejects_surrounding_whitespace() -> None:
    with pytest.raises(ValidationError):
        AuditErrorCountPayload(error_type=" RuntimeError ", count=1)


def test_recovery_action_payload_uses_recovery_action_enum() -> None:
    payload = AuditRecoveryActionCountPayload(action=RecoveryAction.ABORT, count=1)

    assert payload.action is RecoveryAction.ABORT


def mutate_payload(**changes: object) -> dict[str, object]:
    data = valid_payload_data()
    data.update(changes)
    return data


def validate_payload_data(data: dict[str, object]) -> None:
    AuditReportPayload.model_validate_json(json.dumps(data))


def test_top_level_payload_accepts_valid_report() -> None:
    assert isinstance(valid_payload_model(), AuditReportPayload)


def test_top_level_payload_rejects_bad_schema_version() -> None:
    data = mutate_payload(schema_version=999)

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_bad_report_type() -> None:
    data = mutate_payload(report_type="other")

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_corrected_success_above_success() -> None:
    data = valid_payload_data()
    data["correction"]["corrected_success_count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_usage_events_above_success() -> None:
    data = valid_payload_data()
    data["recorded_usage"]["usage_event_count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_failure_classification_mismatch() -> None:
    data = valid_payload_data()
    data["failures"]["retryable_count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_error_count_mismatch() -> None:
    data = valid_payload_data()
    data["errors_by_type"][0]["count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_recovery_count_mismatch() -> None:
    data = valid_payload_data()
    data["recovery_actions"][0]["count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_model_total_mismatch() -> None:
    data = valid_payload_data()
    data["models"][0]["total_events"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_model_success_mismatch() -> None:
    data = valid_payload_data()
    data["models"][0]["success_count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_model_failure_mismatch() -> None:
    data = valid_payload_data()
    data["models"][0]["failure_count"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_model_token_mismatch() -> None:
    data = valid_payload_data()
    data["models"][0]["recorded_total_tokens"] = 99

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_duplicate_error_type() -> None:
    data = valid_payload_data()
    data["errors_by_type"] = [
        {"error_type": "AError", "count": 1},
        {"error_type": "AError", "count": 2},
    ]

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_duplicate_recovery_action() -> None:
    data = valid_payload_data()
    data["recovery_actions"] = [
        {"action": "abort", "count": 1},
        {"action": "abort", "count": 2},
    ]

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_rejects_duplicate_model() -> None:
    data = valid_payload_data()
    data["models"][1]["model"] = data["models"][0]["model"]

    with pytest.raises(ValidationError):
        validate_payload_data(data)


def test_top_level_payload_allows_empty_report() -> None:
    payload = build_audit_report_payload(report=build_audit_report(ParsedAuditEvents((), ())))

    assert payload.summary.total_events == 0
    assert payload.models == []


def test_builder_returns_audit_report_payload() -> None:
    assert isinstance(build_audit_report_payload(report=make_payload_report()), AuditReportPayload)


def test_builder_keeps_json_top_level_keys() -> None:
    assert list(valid_payload_model().model_dump(mode="json")) == [
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


def test_builder_model_dump_json_mode_works() -> None:
    assert valid_payload_model().model_dump(mode="json")["filters"]["status"] == "all"


def test_builder_converts_validation_error_to_audit_report_validation_error() -> None:
    report = AuditReport(
        total_events=1,
        success_count=1,
        failure_count=0,
        success_rate=0.0,
        corrected_success_count=0,
        correction_rate=0.0,
        average_attempts=1.0,
        usage_event_count=0,
        recorded_total_tokens=0,
        average_recorded_tokens=0.0,
        average_elapsed_seconds=0.1,
        max_elapsed_seconds=0.1,
        retryable_failure_count=0,
        non_retryable_failure_count=0,
        errors_by_type=(),
        recovery_actions=(),
        models=(ModelAuditStats("gpt", 1, 1, 0, 1.0, 0, 0.1),),
    )

    with pytest.raises(AuditReportValidationError) as exc_info:
        build_audit_report_payload(report=report)

    assert str(exc_info.value) == "The audit report output failed validation."


def test_builder_validation_error_message_omits_details() -> None:
    report = AuditReport(
        total_events=1,
        success_count=1,
        failure_count=0,
        success_rate=0.0,
        corrected_success_count=0,
        correction_rate=0.0,
        average_attempts=1.0,
        usage_event_count=0,
        recorded_total_tokens=0,
        average_recorded_tokens=0.0,
        average_elapsed_seconds=0.1,
        max_elapsed_seconds=0.1,
        retryable_failure_count=0,
        non_retryable_failure_count=0,
        errors_by_type=(),
        recovery_actions=(),
        models=(ModelAuditStats("PRIVATE-SUMMARY", 1, 1, 0, 1.0, 0, 0.1),),
    )

    with pytest.raises(AuditReportValidationError) as exc_info:
        build_audit_report_payload(report=report)

    assert "PRIVATE-SUMMARY" not in str(exc_info.value)


def test_validate_audit_report_json_success() -> None:
    payload = validate_audit_report_json(format_audit_report_json(make_payload_report()))

    assert isinstance(payload, AuditReportPayload)


def test_validate_audit_report_json_rejects_bad_structure() -> None:
    with pytest.raises(AuditReportValidationError):
        validate_audit_report_json(json.dumps({"schema_version": 1}))


def test_validate_audit_report_json_rejects_bad_syntax() -> None:
    with pytest.raises(AuditReportValidationError):
        validate_audit_report_json("{PRIVATE-SUMMARY")


def test_validate_audit_report_json_error_message_omits_raw_json() -> None:
    with pytest.raises(AuditReportValidationError) as exc_info:
        validate_audit_report_json("{PRIVATE-SUMMARY")

    assert str(exc_info.value) == "The audit report JSON failed validation."
    assert "PRIVATE-SUMMARY" not in str(exc_info.value)


def test_text_formatter_result_is_unchanged_by_payload_validation() -> None:
    report = make_payload_report()
    before = format_audit_report(report)

    build_audit_report_payload(report=report)

    assert format_audit_report(report) == before


def test_payload_json_schema_is_object() -> None:
    schema = AuditReportPayload.model_json_schema()

    assert schema["type"] == "object"


def test_payload_json_schema_forbids_extra_properties() -> None:
    schema = AuditReportPayload.model_json_schema()

    assert schema["additionalProperties"] is False


def test_payload_json_schema_required_top_level_fields() -> None:
    schema = AuditReportPayload.model_json_schema()

    assert set(schema["required"]) == set(valid_payload_data())


def test_payload_json_schema_fixes_schema_version() -> None:
    schema_text = json.dumps(AuditReportPayload.model_json_schema())

    assert "const" in schema_text
    assert str(AUDIT_REPORT_SCHEMA_VERSION) in schema_text


def test_payload_json_schema_fixes_report_type() -> None:
    schema_text = json.dumps(AuditReportPayload.model_json_schema())

    assert "structured_analysis_audit_report" in schema_text


def test_payload_json_schema_includes_success_rate_bounds() -> None:
    schema_text = json.dumps(AuditReportSummaryPayload.model_json_schema())

    assert "success_rate" in schema_text
    assert "maximum" in schema_text
    assert "minimum" in schema_text


@pytest.mark.parametrize(
    "field_name",
    [
        "user_input",
        "response_id",
        "request_id",
        "private_summary",
        "keyword",
        "review_reason",
        "api_key",
    ],
)
def test_payload_rejects_sensitive_extra_fields(field_name: str) -> None:
    data = valid_payload_data()
    data[field_name] = "sk-test-do-not-log"

    with pytest.raises(ValidationError):
        AuditReportPayload.model_validate_json(json.dumps(data))
