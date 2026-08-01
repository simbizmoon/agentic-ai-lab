"""Read structured analysis audit logs and build local reports."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.exceptions import (
    AuditLogParseError,
    AuditLogReadError,
    InvalidAuditEventError,
    UnsupportedAuditSchemaError,
)
from app.observability import AUDIT_SCHEMA_VERSION


@dataclass(frozen=True)
class ParsedSuccessEvent:
    model: str
    attempts: int
    correction_attempted: bool
    recorded_total_tokens: int | None
    total_elapsed_seconds: float


@dataclass(frozen=True)
class ParsedFailureEvent:
    model: str
    error_type: str
    recovery_action: str
    retryable: bool


@dataclass(frozen=True)
class ParsedAuditEvents:
    successes: tuple[ParsedSuccessEvent, ...]
    failures: tuple[ParsedFailureEvent, ...]


@dataclass(frozen=True)
class ModelAuditStats:
    model: str
    total_events: int
    success_count: int
    failure_count: int
    success_rate: float
    recorded_total_tokens: int
    average_success_elapsed_seconds: float


@dataclass(frozen=True)
class AuditReport:
    total_events: int
    success_count: int
    failure_count: int
    success_rate: float
    corrected_success_count: int
    correction_rate: float
    average_attempts: float
    usage_event_count: int
    recorded_total_tokens: int
    average_recorded_tokens: float
    average_elapsed_seconds: float
    max_elapsed_seconds: float
    retryable_failure_count: int
    non_retryable_failure_count: int
    errors_by_type: tuple[tuple[str, int], ...]
    recovery_actions: tuple[tuple[str, int], ...]
    models: tuple[ModelAuditStats, ...]


def read_audit_events(
    path: Path,
) -> ParsedAuditEvents:
    successes: list[ParsedSuccessEvent] = []
    failures: list[ParsedFailureEvent] = []

    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                payload = _parse_json_line(line, line_number=line_number)
                event = _parse_event(payload, line_number=line_number)
                if isinstance(event, ParsedSuccessEvent):
                    successes.append(event)
                else:
                    failures.append(event)
    except OSError as error:
        raise AuditLogReadError(
            "Failed to read the structured analysis audit log."
        ) from error

    return ParsedAuditEvents(successes=tuple(successes), failures=tuple(failures))


def build_audit_report(
    events: ParsedAuditEvents,
) -> AuditReport:
    successes = events.successes
    failures = events.failures
    total_events = len(successes) + len(failures)
    success_count = len(successes)
    failure_count = len(failures)
    corrected_success_count = sum(1 for event in successes if event.correction_attempted)
    usage_tokens = [
        event.recorded_total_tokens
        for event in successes
        if event.recorded_total_tokens is not None
    ]
    elapsed_values = [event.total_elapsed_seconds for event in successes]
    error_counter = Counter(event.error_type for event in failures)
    recovery_counter = Counter(event.recovery_action for event in failures)

    return AuditReport(
        total_events=total_events,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=_divide(success_count, total_events),
        corrected_success_count=corrected_success_count,
        correction_rate=_divide(corrected_success_count, success_count),
        average_attempts=_divide(sum(event.attempts for event in successes), success_count),
        usage_event_count=len(usage_tokens),
        recorded_total_tokens=sum(usage_tokens),
        average_recorded_tokens=_divide(sum(usage_tokens), len(usage_tokens)),
        average_elapsed_seconds=_divide(sum(elapsed_values), len(elapsed_values)),
        max_elapsed_seconds=max(elapsed_values, default=0.0),
        retryable_failure_count=sum(1 for event in failures if event.retryable),
        non_retryable_failure_count=sum(1 for event in failures if not event.retryable),
        errors_by_type=_sorted_counter(error_counter),
        recovery_actions=_sorted_counter(recovery_counter),
        models=_build_model_stats(successes, failures),
    )


def format_audit_report(
    report: AuditReport,
) -> str:
    lines = [
        "Structured Analysis Audit Report",
        "",
        "Summary",
        f"  Total Events: {report.total_events}",
        f"  Successes: {report.success_count}",
        f"  Failures: {report.failure_count}",
        f"  Success Rate: {_format_percent(report.success_rate)}",
        "",
        "Correction",
        f"  Corrected Successes: {report.corrected_success_count}",
        f"  Correction Rate: {_format_percent(report.correction_rate)}",
        f"  Average Attempts: {report.average_attempts:.3f}",
        "",
        "Recorded Usage",
        f"  Usage Events: {report.usage_event_count}",
        f"  Total Tokens: {report.recorded_total_tokens}",
        f"  Average Tokens: {report.average_recorded_tokens:.3f}",
        "",
        "Latency",
        f"  Average Success Seconds: {report.average_elapsed_seconds:.3f}",
        f"  Max Success Seconds: {report.max_elapsed_seconds:.3f}",
        "",
        "Failures",
        f"  Retryable: {report.retryable_failure_count}",
        f"  Non-Retryable: {report.non_retryable_failure_count}",
        "",
        "Errors By Type",
    ]
    lines.extend(_format_pairs(report.errors_by_type))
    lines.append("")
    lines.append("Recovery Actions")
    lines.extend(_format_pairs(report.recovery_actions))
    lines.append("")
    lines.append("Models")
    if report.models:
        for model in report.models:
            lines.append(
                "  "
                f"{model.model}: total={model.total_events}, "
                f"success={model.success_count}, failure={model.failure_count}, "
                f"success_rate={_format_percent(model.success_rate)}, "
                f"tokens={model.recorded_total_tokens}, "
                f"avg_latency={model.average_success_elapsed_seconds:.3f}"
            )
    else:
        lines.append("  None")

    return "\n".join(lines)


def _parse_json_line(line: str, *, line_number: int) -> dict[str, Any]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as error:
        raise AuditLogParseError(
            f"Failed to parse audit log JSON on line {line_number}."
        ) from error

    if not isinstance(payload, dict):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: payload must be an object."
        )
    return payload


def _parse_event(
    payload: dict[str, Any],
    *,
    line_number: int,
) -> ParsedSuccessEvent | ParsedFailureEvent:
    for field_name in (
        "schema_version",
        "event_type",
        "timestamp_utc",
        "status",
        "model",
    ):
        _require_field(payload, field_name, line_number=line_number)

    schema_version = payload["schema_version"]
    if not _is_int(schema_version) or schema_version != AUDIT_SCHEMA_VERSION:
        raise UnsupportedAuditSchemaError(
            f"Unsupported audit schema version on line {line_number}."
        )

    event_type = payload["event_type"]
    status = payload["status"]
    model = payload["model"]
    timestamp_utc = payload["timestamp_utc"]
    if not _is_non_empty_string(model):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: model is invalid."
        )
    if not isinstance(timestamp_utc, str) or not timestamp_utc.strip():
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: timestamp is invalid."
        )

    if event_type == "structured_analysis_completed":
        if status != "success":
            raise InvalidAuditEventError(
                f"Invalid audit event on line {line_number}: event status mismatch."
            )
        return _parse_success_event(payload, line_number=line_number)

    if event_type == "structured_analysis_failed":
        if status != "failure":
            raise InvalidAuditEventError(
                f"Invalid audit event on line {line_number}: event status mismatch."
            )
        return _parse_failure_event(payload, line_number=line_number)

    raise InvalidAuditEventError(
        f"Invalid audit event on line {line_number}: unknown event type."
    )


def _parse_success_event(
    payload: dict[str, Any],
    *,
    line_number: int,
) -> ParsedSuccessEvent:
    for field_name in (
        "attempts",
        "correction_attempted",
        "recorded_usage",
        "total_elapsed_seconds",
        "response_ids",
        "final_response_id",
        "final_request_id",
        "budget",
        "keyword_count",
        "requires_review",
        "review_reason_present",
    ):
        _require_field(payload, field_name, line_number=line_number)

    attempts = payload["attempts"]
    if not _is_int(attempts) or attempts < 1:
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: attempts is invalid."
        )

    correction_attempted = payload["correction_attempted"]
    if not isinstance(correction_attempted, bool):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: correction flag is invalid."
        )

    elapsed_seconds = payload["total_elapsed_seconds"]
    if not _is_number(elapsed_seconds) or elapsed_seconds < 0:
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: latency is invalid."
        )

    recorded_total_tokens = _parse_recorded_total_tokens(
        payload["recorded_usage"],
        line_number=line_number,
    )

    return ParsedSuccessEvent(
        model=payload["model"],
        attempts=attempts,
        correction_attempted=correction_attempted,
        recorded_total_tokens=recorded_total_tokens,
        total_elapsed_seconds=float(elapsed_seconds),
    )


def _parse_failure_event(
    payload: dict[str, Any],
    *,
    line_number: int,
) -> ParsedFailureEvent:
    for field_name in ("error_type", "recovery_action", "retryable", "budget"):
        _require_field(payload, field_name, line_number=line_number)

    error_type = payload["error_type"]
    recovery_action = payload["recovery_action"]
    retryable = payload["retryable"]
    if not _is_non_empty_string(error_type):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: error type is invalid."
        )
    if not _is_non_empty_string(recovery_action):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: recovery action is invalid."
        )
    if not isinstance(retryable, bool):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: retryable flag is invalid."
        )

    return ParsedFailureEvent(
        model=payload["model"],
        error_type=error_type,
        recovery_action=recovery_action,
        retryable=retryable,
    )


def _parse_recorded_total_tokens(
    recorded_usage: object,
    *,
    line_number: int,
) -> int | None:
    if recorded_usage is None:
        return None
    if not isinstance(recorded_usage, dict):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: recorded usage is invalid."
        )
    _require_field(recorded_usage, "total_tokens", line_number=line_number)
    total_tokens = recorded_usage["total_tokens"]
    if not _is_int(total_tokens) or total_tokens < 0:
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: token count is invalid."
        )
    return total_tokens


def _build_model_stats(
    successes: tuple[ParsedSuccessEvent, ...],
    failures: tuple[ParsedFailureEvent, ...],
) -> tuple[ModelAuditStats, ...]:
    success_by_model: dict[str, list[ParsedSuccessEvent]] = defaultdict(list)
    failure_by_model: Counter[str] = Counter()
    for event in successes:
        success_by_model[event.model].append(event)
    for event in failures:
        failure_by_model[event.model] += 1

    model_names = sorted(set(success_by_model) | set(failure_by_model))
    stats = []
    for model in model_names:
        model_successes = success_by_model[model]
        success_count = len(model_successes)
        failure_count = failure_by_model[model]
        total_events = success_count + failure_count
        elapsed_values = [event.total_elapsed_seconds for event in model_successes]
        stats.append(
            ModelAuditStats(
                model=model,
                total_events=total_events,
                success_count=success_count,
                failure_count=failure_count,
                success_rate=_divide(success_count, total_events),
                recorded_total_tokens=sum(
                    event.recorded_total_tokens or 0 for event in model_successes
                ),
                average_success_elapsed_seconds=_divide(
                    sum(elapsed_values),
                    len(elapsed_values),
                ),
            )
        )
    return tuple(stats)


def _require_field(
    payload: dict[str, Any],
    field_name: str,
    *,
    line_number: int,
) -> None:
    if field_name not in payload:
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: missing field {field_name}."
        )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _divide(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / denominator


def _sorted_counter(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_pairs(pairs: tuple[tuple[str, int], ...]) -> list[str]:
    if not pairs:
        return ["  None"]
    return [f"  {name}: {count}" for name, count in pairs]
