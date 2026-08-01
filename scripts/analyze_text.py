"""Run a minimal OpenAI structured text analysis request."""

from __future__ import annotations

import sys
from pathlib import Path

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.budget import ExecutionBudget
from app.config import load_settings
from app.exceptions import AuditLogError, ExecutionBudgetError, StructuredAnalysisError
from app.observability import (
    append_audit_event,
    build_failure_event,
    build_success_event,
    current_utc_timestamp,
)
from app.recovery import RecoveryAction, RecoveryDecision, decide_recovery
from app.services.openai_client import create_openai_client
from app.services.structured_analysis import analyze_text_with_correction

ANALYSIS_INPUT = (
    "착석 상태를 자동으로 감지하고 장시간 착석 시 "
    "사용자에게 진동 알림을 제공하는 시스템이다."
)

ANALYSIS_BUDGET = ExecutionBudget(
    max_attempts=2,
    max_recorded_tokens=2000,
    max_elapsed_seconds=30.0,
)

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "structured_analysis.jsonl"


def exit_code_for_recovery(
    decision: RecoveryDecision,
) -> int:
    if decision.action is RecoveryAction.MODIFY_REQUEST:
        return 1
    if decision.action is RecoveryAction.RETRY_LATER:
        return 2
    if decision.action is RecoveryAction.FIX_CONFIGURATION:
        return 3
    if decision.action is RecoveryAction.HUMAN_REVIEW:
        return 4
    return 5


def print_recovery_decision(
    decision: RecoveryDecision,
) -> None:
    print("[ERROR] Structured analysis failed")
    print(f"Action: {decision.action.value}")
    print(f"Retryable: {str(decision.retryable).lower()}")
    print(f"Reason: {decision.reason}")


def print_usage(result_usage: object) -> None:
    if result_usage is None:
        print("Recorded Usage: unavailable")
        return

    print("Recorded Usage:")
    print(f"  Input Tokens: {result_usage.input_tokens}")
    print(f"  Cached Input Tokens: {result_usage.cached_input_tokens}")
    print(f"  Output Tokens: {result_usage.output_tokens}")
    print(f"  Reasoning Tokens: {result_usage.reasoning_tokens}")
    print(f"  Total Tokens: {result_usage.total_tokens}")


def handle_known_error(error: BaseException, *, model: str) -> int:
    decision = decide_recovery(error)
    try:
        event = build_failure_event(
            model=model,
            error=error,
            decision=decision,
            budget=ANALYSIS_BUDGET,
            timestamp_utc=current_utc_timestamp(),
        )
        append_audit_event(path=AUDIT_LOG_PATH, event=event)
    except AuditLogError as audit_error:
        audit_decision = decide_recovery(audit_error)
        print_recovery_decision(audit_decision)
        return exit_code_for_recovery(audit_decision)

    print_recovery_decision(decision)
    return exit_code_for_recovery(decision)


def main() -> int:
    model = "unavailable"
    try:
        settings = load_settings()
        model = settings.openai_model
        client = create_openai_client(settings)
        try:
            execution = analyze_text_with_correction(
                client,
                model=settings.openai_model,
                user_input=ANALYSIS_INPUT,
                budget=ANALYSIS_BUDGET,
            )
            result = execution.result
            success_event = build_success_event(
                model=settings.openai_model,
                execution=execution,
                budget=ANALYSIS_BUDGET,
                timestamp_utc=current_utc_timestamp(),
            )
            append_audit_event(path=AUDIT_LOG_PATH, event=success_event)
        finally:
            client.close()
    except AuditLogError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)
    except ValueError as exc:
        return handle_known_error(exc, model=model)
    except ExecutionBudgetError as exc:
        return handle_known_error(exc, model=model)
    except StructuredAnalysisError as exc:
        return handle_known_error(exc, model=model)
    except openai.APITimeoutError as exc:
        return handle_known_error(exc, model=model)
    except openai.APIConnectionError as exc:
        return handle_known_error(exc, model=model)
    except openai.APIStatusError as exc:
        return handle_known_error(exc, model=model)

    recorded_tokens = 0
    if execution.total_usage is not None:
        recorded_tokens = execution.total_usage.total_tokens

    print("[OK] Structured analysis received")
    print(f"Model: {settings.openai_model}")
    print(f"Response ID: {result.response_id}")
    print(f"Request ID: {result.request_id or 'unavailable'}")
    print("Budget:")
    print(f"  Max Attempts: {ANALYSIS_BUDGET.max_attempts}")
    print(f"  Max Recorded Tokens: {ANALYSIS_BUDGET.max_recorded_tokens}")
    print(f"  Max Elapsed Seconds: {ANALYSIS_BUDGET.max_elapsed_seconds:.3f}")
    print("Execution:")
    print(f"  Attempts: {execution.attempts}")
    print(f"  Correction Attempted: {str(execution.correction_attempted).lower()}")
    print(f"  Recorded Tokens: {recorded_tokens}")
    print(f"  Total Elapsed Seconds: {execution.total_elapsed_seconds:.3f}")
    print_usage(execution.total_usage)
    print("Analysis:")
    print(f"  Topic: {result.analysis.topic}")
    print(f"  Summary: {result.analysis.summary}")
    print(f"  Sentiment: {result.analysis.sentiment.value}")
    print("  Keywords:")
    for keyword in result.analysis.keywords:
        print(f"    - {keyword}")
    print(f"  Requires Review: {str(result.analysis.requires_review).lower()}")
    print(f"  Review Reason: {result.analysis.review_reason or 'unavailable'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
