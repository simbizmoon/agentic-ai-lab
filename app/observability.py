"""Safe JSONL audit events for structured analysis runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.budget import ExecutionBudget
from app.exceptions import AuditLogError
from app.recovery import RecoveryDecision
from app.services.structured_analysis import StructuredAnalysisExecution
from app.services.text_generation import TokenUsage

AUDIT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AuditTokenUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class AuditBudget:
    max_attempts: int
    max_recorded_tokens: int
    max_elapsed_seconds: float


@dataclass(frozen=True)
class StructuredAnalysisSuccessEvent:
    schema_version: int
    event_type: str
    timestamp_utc: str
    status: str
    model: str
    attempts: int
    correction_attempted: bool
    recorded_usage: AuditTokenUsage | None
    total_elapsed_seconds: float
    response_ids: tuple[str, ...]
    final_response_id: str
    final_request_id: str | None
    budget: AuditBudget
    keyword_count: int
    requires_review: bool
    review_reason_present: bool


@dataclass(frozen=True)
class StructuredAnalysisFailureEvent:
    schema_version: int
    event_type: str
    timestamp_utc: str
    status: str
    model: str
    error_type: str
    recovery_action: str
    retryable: bool
    budget: AuditBudget


def current_utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def to_audit_token_usage(
    usage: TokenUsage | None,
) -> AuditTokenUsage | None:
    if usage is None:
        return None

    return AuditTokenUsage(
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        total_tokens=usage.total_tokens,
    )


def to_audit_budget(
    budget: ExecutionBudget,
) -> AuditBudget:
    return AuditBudget(
        max_attempts=budget.max_attempts,
        max_recorded_tokens=budget.max_recorded_tokens,
        max_elapsed_seconds=budget.max_elapsed_seconds,
    )


def build_success_event(
    *,
    model: str,
    execution: StructuredAnalysisExecution,
    budget: ExecutionBudget,
    timestamp_utc: str,
) -> StructuredAnalysisSuccessEvent:
    analysis = execution.result.analysis

    return StructuredAnalysisSuccessEvent(
        schema_version=AUDIT_SCHEMA_VERSION,
        event_type="structured_analysis_completed",
        timestamp_utc=timestamp_utc,
        status="success",
        model=model,
        attempts=execution.attempts,
        correction_attempted=execution.correction_attempted,
        recorded_usage=to_audit_token_usage(execution.total_usage),
        total_elapsed_seconds=execution.total_elapsed_seconds,
        response_ids=execution.response_ids,
        final_response_id=execution.result.response_id,
        final_request_id=execution.result.request_id,
        budget=to_audit_budget(budget),
        keyword_count=len(analysis.keywords),
        requires_review=analysis.requires_review,
        review_reason_present=analysis.review_reason is not None,
    )


def build_failure_event(
    *,
    model: str,
    error: BaseException,
    decision: RecoveryDecision,
    budget: ExecutionBudget,
    timestamp_utc: str,
) -> StructuredAnalysisFailureEvent:
    return StructuredAnalysisFailureEvent(
        schema_version=AUDIT_SCHEMA_VERSION,
        event_type="structured_analysis_failed",
        timestamp_utc=timestamp_utc,
        status="failure",
        model=model,
        error_type=type(error).__name__,
        recovery_action=decision.action.value,
        retryable=decision.retryable,
        budget=to_audit_budget(budget),
    )


def append_audit_event(
    *,
    path: Path,
    event: StructuredAnalysisSuccessEvent | StructuredAnalysisFailureEvent,
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(event)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{line}\n")
    except OSError as error:
        raise AuditLogError(
            "Failed to write the structured analysis audit log."
        ) from error
