"""Read structured analysis audit logs and build local reports."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isclose
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
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

AUDIT_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ParsedSuccessEvent:
    model: str
    timestamp_utc: datetime
    attempts: int
    correction_attempted: bool
    recorded_total_tokens: int | None
    total_elapsed_seconds: float


@dataclass(frozen=True)
class ParsedFailureEvent:
    model: str
    timestamp_utc: datetime
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


class AuditReportFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


class AuditStatusFilter(str, Enum):
    ALL = "all"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True)
class AuditReportFilter:
    since: datetime | None = None
    until: datetime | None = None
    model: str | None = None
    status: AuditStatusFilter = AuditStatusFilter.ALL

    def __post_init__(self) -> None:
        if self.since is not None and not _is_timezone_aware(self.since):
            raise ValueError("since must be timezone-aware")
        if self.until is not None and not _is_timezone_aware(self.until):
            raise ValueError("until must be timezone-aware")
        if self.since is not None and self.until is not None and self.since >= self.until:
            raise ValueError("since must be earlier than until")
        if self.model is not None:
            if not self.model.strip():
                raise ValueError("model must not be empty")
            if self.model != self.model.strip():
                raise ValueError("model must not include surrounding whitespace")


class AuditPayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AuditReportFilterPayload(AuditPayloadModel):
    since: str | None
    until: str | None
    model: str | None
    status: AuditStatusFilter


class AuditReportSummaryPayload(AuditPayloadModel):
    total_events: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_summary_counts(self) -> Self:
        if self.total_events != self.success_count + self.failure_count:
            raise ValueError("total_events must equal success_count plus failure_count")
        expected_rate = _divide(self.success_count, self.total_events)
        if not isclose(self.success_rate, expected_rate):
            raise ValueError("success_rate must match success_count divided by total_events")
        return self


class AuditReportCorrectionPayload(AuditPayloadModel):
    corrected_success_count: int = Field(ge=0)
    correction_rate: float = Field(ge=0.0, le=1.0)
    average_attempts: float = Field(ge=0.0)


class AuditReportUsagePayload(AuditPayloadModel):
    usage_event_count: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    average_tokens: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_average_tokens(self) -> Self:
        expected_average = _divide(self.total_tokens, self.usage_event_count)
        if not isclose(self.average_tokens, expected_average):
            raise ValueError("average_tokens must match total_tokens divided by usage_event_count")
        return self


class AuditReportLatencyPayload(AuditPayloadModel):
    average_success_elapsed_seconds: float = Field(ge=0.0)
    maximum_success_elapsed_seconds: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_latency_order(self) -> Self:
        if self.average_success_elapsed_seconds > self.maximum_success_elapsed_seconds:
            raise ValueError("average latency must not exceed maximum latency")
        return self


class AuditReportFailuresPayload(AuditPayloadModel):
    retryable_count: int = Field(ge=0)
    non_retryable_count: int = Field(ge=0)


class AuditErrorCountPayload(AuditPayloadModel):
    error_type: str = Field(min_length=1)
    count: int = Field(ge=1)

    @field_validator("error_type")
    @classmethod
    def reject_surrounding_error_type_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("error_type must not include surrounding whitespace")
        return value


class AuditRecoveryActionCountPayload(AuditPayloadModel):
    action: RecoveryAction
    count: int = Field(ge=1)


class AuditModelStatsPayload(AuditPayloadModel):
    model: str = Field(min_length=1)
    total_events: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    recorded_total_tokens: int = Field(ge=0)
    average_success_elapsed_seconds: float = Field(ge=0.0)

    @field_validator("model")
    @classmethod
    def reject_surrounding_model_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("model must not include surrounding whitespace")
        return value

    @model_validator(mode="after")
    def validate_model_stats(self) -> Self:
        if self.total_events != self.success_count + self.failure_count:
            raise ValueError("model total_events must equal success_count plus failure_count")
        expected_rate = _divide(self.success_count, self.total_events)
        if not isclose(self.success_rate, expected_rate):
            raise ValueError("model success_rate must match success_count divided by total_events")
        return self


class AuditReportPayload(AuditPayloadModel):
    schema_version: Literal[1]
    report_type: Literal["structured_analysis_audit_report"]
    filters: AuditReportFilterPayload
    summary: AuditReportSummaryPayload
    correction: AuditReportCorrectionPayload
    recorded_usage: AuditReportUsagePayload
    latency: AuditReportLatencyPayload
    failures: AuditReportFailuresPayload
    errors_by_type: list[AuditErrorCountPayload]
    recovery_actions: list[AuditRecoveryActionCountPayload]
    models: list[AuditModelStatsPayload]

    @model_validator(mode="after")
    def validate_report_invariants(self) -> Self:
        if self.correction.corrected_success_count > self.summary.success_count:
            raise ValueError("corrected_success_count must not exceed success_count")
        if self.recorded_usage.usage_event_count > self.summary.success_count:
            raise ValueError("usage_event_count must not exceed success_count")
        failure_total = self.failures.retryable_count + self.failures.non_retryable_count
        if failure_total != self.summary.failure_count:
            raise ValueError("failure counts must equal failure_count")
        if sum(item.count for item in self.errors_by_type) != self.summary.failure_count:
            raise ValueError("error counts must equal failure_count")
        if sum(item.count for item in self.recovery_actions) != self.summary.failure_count:
            raise ValueError("recovery counts must equal failure_count")
        if sum(model.total_events for model in self.models) != self.summary.total_events:
            raise ValueError("model total_events must equal report total_events")
        if sum(model.success_count for model in self.models) != self.summary.success_count:
            raise ValueError("model success_count must equal report success_count")
        if sum(model.failure_count for model in self.models) != self.summary.failure_count:
            raise ValueError("model failure_count must equal report failure_count")
        if sum(model.recorded_total_tokens for model in self.models) != self.recorded_usage.total_tokens:
            raise ValueError("model tokens must equal report total_tokens")
        _ensure_unique(
            [item.error_type for item in self.errors_by_type],
            "error_type values must be unique",
        )
        _ensure_unique(
            [item.action for item in self.recovery_actions],
            "recovery action values must be unique",
        )
        _ensure_unique(
            [model.model for model in self.models],
            "model values must be unique",
        )
        return self


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


def filter_audit_events(
    *,
    events: ParsedAuditEvents,
    report_filter: AuditReportFilter,
) -> ParsedAuditEvents:
    successes = events.successes
    failures = events.failures

    if report_filter.status is AuditStatusFilter.FAILURE:
        successes = ()
    else:
        successes = tuple(
            event for event in successes if _event_matches_filter(event, report_filter)
        )

    if report_filter.status is AuditStatusFilter.SUCCESS:
        failures = ()
    else:
        failures = tuple(
            event for event in failures if _event_matches_filter(event, report_filter)
        )

    return ParsedAuditEvents(successes=successes, failures=failures)


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


def build_audit_report_payload(
    *,
    report: AuditReport,
    report_filter: AuditReportFilter | None = None,
) -> AuditReportPayload:
    if report_filter is None:
        report_filter = AuditReportFilter()

    try:
        return AuditReportPayload(
            schema_version=AUDIT_REPORT_SCHEMA_VERSION,
            report_type="structured_analysis_audit_report",
            filters=AuditReportFilterPayload(
                since=_payload_filter_datetime(report_filter.since),
                until=_payload_filter_datetime(report_filter.until),
                model=report_filter.model,
                status=report_filter.status,
            ),
            summary=AuditReportSummaryPayload(
                total_events=report.total_events,
                success_count=report.success_count,
                failure_count=report.failure_count,
                success_rate=report.success_rate,
            ),
            correction=AuditReportCorrectionPayload(
                corrected_success_count=report.corrected_success_count,
                correction_rate=report.correction_rate,
                average_attempts=report.average_attempts,
            ),
            recorded_usage=AuditReportUsagePayload(
                usage_event_count=report.usage_event_count,
                total_tokens=report.recorded_total_tokens,
                average_tokens=report.average_recorded_tokens,
            ),
            latency=AuditReportLatencyPayload(
                average_success_elapsed_seconds=report.average_elapsed_seconds,
                maximum_success_elapsed_seconds=report.max_elapsed_seconds,
            ),
            failures=AuditReportFailuresPayload(
                retryable_count=report.retryable_failure_count,
                non_retryable_count=report.non_retryable_failure_count,
            ),
            errors_by_type=[
                AuditErrorCountPayload(error_type=error_type, count=count)
                for error_type, count in report.errors_by_type
            ],
            recovery_actions=[
                AuditRecoveryActionCountPayload(
                    action=RecoveryAction(action),
                    count=count,
                )
                for action, count in report.recovery_actions
            ],
            models=[
                AuditModelStatsPayload(
                    model=model.model,
                    total_events=model.total_events,
                    success_count=model.success_count,
                    failure_count=model.failure_count,
                    success_rate=model.success_rate,
                    recorded_total_tokens=model.recorded_total_tokens,
                    average_success_elapsed_seconds=model.average_success_elapsed_seconds,
                )
                for model in report.models
            ],
        )
    except (ValidationError, ValueError) as error:
        raise AuditReportValidationError(
            "The audit report output failed validation."
        ) from error


def format_audit_report_json(
    report: AuditReport,
    *,
    report_filter: AuditReportFilter | None = None,
) -> str:
    payload = build_audit_report_payload(
        report=report,
        report_filter=report_filter,
    )
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def validate_audit_report_json(
    json_text: str,
) -> AuditReportPayload:
    try:
        return AuditReportPayload.model_validate_json(json_text)
    except ValidationError as error:
        raise AuditReportValidationError(
            "The audit report JSON failed validation."
        ) from error


def render_audit_report(
    *,
    report: AuditReport,
    report_filter: AuditReportFilter,
    report_format: AuditReportFormat,
) -> str:
    if report_format is AuditReportFormat.TEXT:
        return format_audit_report(report, report_filter=report_filter)
    if report_format is AuditReportFormat.JSON:
        return format_audit_report_json(report, report_filter=report_filter)
    raise ValueError("Unsupported audit report format")


def format_audit_report(
    report: AuditReport,
    *,
    report_filter: AuditReportFilter | None = None,
) -> str:
    if report_filter is None:
        report_filter = AuditReportFilter()

    lines = [
        "Structured Analysis Audit Report",
        "",
        "Filters",
        f"  Since: {_format_filter_datetime(report_filter.since)}",
        f"  Until: {_format_filter_datetime(report_filter.until)}",
        f"  Model: {report_filter.model or 'all'}",
        f"  Status: {report_filter.status.value}",
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
    if not _is_non_empty_string(model):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: model is invalid."
        )
    timestamp_utc = _parse_timestamp(payload["timestamp_utc"], line_number=line_number)

    if event_type == "structured_analysis_completed":
        if status != "success":
            raise InvalidAuditEventError(
                f"Invalid audit event on line {line_number}: event status mismatch."
            )
        return _parse_success_event(
            payload,
            timestamp_utc=timestamp_utc,
            line_number=line_number,
        )

    if event_type == "structured_analysis_failed":
        if status != "failure":
            raise InvalidAuditEventError(
                f"Invalid audit event on line {line_number}: event status mismatch."
            )
        return _parse_failure_event(
            payload,
            timestamp_utc=timestamp_utc,
            line_number=line_number,
        )

    raise InvalidAuditEventError(
        f"Invalid audit event on line {line_number}: unknown event type."
    )


def _parse_success_event(
    payload: dict[str, Any],
    *,
    timestamp_utc: datetime,
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
        timestamp_utc=timestamp_utc,
        attempts=attempts,
        correction_attempted=correction_attempted,
        recorded_total_tokens=recorded_total_tokens,
        total_elapsed_seconds=float(elapsed_seconds),
    )


def _parse_failure_event(
    payload: dict[str, Any],
    *,
    timestamp_utc: datetime,
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
        timestamp_utc=timestamp_utc,
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


def _parse_timestamp(value: object, *, line_number: int) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: timestamp is invalid."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: timestamp is invalid."
        ) from error
    if not _is_timezone_aware(parsed):
        raise InvalidAuditEventError(
            f"Invalid audit event on line {line_number}: timestamp is invalid."
        )
    return parsed.astimezone(UTC)


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


def _event_matches_filter(
    event: ParsedSuccessEvent | ParsedFailureEvent,
    report_filter: AuditReportFilter,
) -> bool:
    if report_filter.since is not None and event.timestamp_utc < report_filter.since:
        return False
    if report_filter.until is not None and event.timestamp_utc >= report_filter.until:
        return False
    return report_filter.model is None or event.model == report_filter.model


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


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _divide(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / denominator


def _sorted_counter(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_filter_datetime(value: datetime | None) -> str:
    if value is None:
        return "all"
    return value.astimezone(UTC).isoformat()


def _payload_filter_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _ensure_unique(values: list[object], message: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(message)


def _format_pairs(pairs: tuple[tuple[str, int], ...]) -> list[str]:
    if not pairs:
        return ["  None"]
    return [f"  {name}: {count}" for name, count in pairs]
