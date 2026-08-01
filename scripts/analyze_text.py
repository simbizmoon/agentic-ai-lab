"""Run a minimal OpenAI structured text analysis request."""

from __future__ import annotations

import sys
from pathlib import Path

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_settings
from app.exceptions import StructuredAnalysisError
from app.recovery import RecoveryAction, RecoveryDecision, decide_recovery
from app.services.openai_client import create_openai_client
from app.services.structured_analysis import analyze_text_with_correction

ANALYSIS_INPUT = (
    "착석 상태를 자동으로 감지하고 장시간 착석 시 "
    "사용자에게 진동 알림을 제공하는 시스템이다."
)


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
        print("Usage: unavailable")
        return

    print("Usage:")
    print(f"  Input Tokens: {result_usage.input_tokens}")
    print(f"  Cached Input Tokens: {result_usage.cached_input_tokens}")
    print(f"  Output Tokens: {result_usage.output_tokens}")
    print(f"  Reasoning Tokens: {result_usage.reasoning_tokens}")
    print(f"  Total Tokens: {result_usage.total_tokens}")


def main() -> int:
    try:
        settings = load_settings()
        client = create_openai_client(settings)
        try:
            result = analyze_text_with_correction(
                client,
                model=settings.openai_model,
                user_input=ANALYSIS_INPUT,
            )
        finally:
            client.close()
    except ValueError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)
    except StructuredAnalysisError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)
    except openai.APITimeoutError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)
    except openai.APIConnectionError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)
    except openai.APIStatusError as exc:
        decision = decide_recovery(exc)
        print_recovery_decision(decision)
        return exit_code_for_recovery(decision)

    print("[OK] Structured analysis received")
    print(f"Model: {settings.openai_model}")
    print(f"Response ID: {result.response_id}")
    print(f"Request ID: {result.request_id or 'unavailable'}")
    print_usage(result.usage)
    print(f"Elapsed Seconds: {result.elapsed_seconds:.3f}")
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
