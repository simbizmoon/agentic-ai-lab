"""Analyze a local text document with AIRA Structured Outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_settings
from app.exceptions import StructuredAnalysisError
from app.recovery import RecoveryAction, decide_recovery
from app.services.document_analysis import analyze_document
from app.services.openai_client import create_openai_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze a local UTF-8 text document.",
    )
    parser.add_argument(
        "document",
        type=Path,
        help="Path to a UTF-8 text document.",
    )
    return parser


def exit_code_for_action(action: RecoveryAction) -> int:
    if action is RecoveryAction.MODIFY_REQUEST:
        return 1
    if action is RecoveryAction.RETRY_LATER:
        return 2
    if action is RecoveryAction.FIX_CONFIGURATION:
        return 3
    if action is RecoveryAction.HUMAN_REVIEW:
        return 4
    return 5


def print_error(error: BaseException) -> int:
    decision = decide_recovery(error)

    print("[ERROR] Document analysis failed")
    print(f"Action: {decision.action.value}")
    print(f"Retryable: {str(decision.retryable).lower()}")
    print(f"Reason: {decision.reason}")

    return exit_code_for_action(decision.action)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        document_text = args.document.read_text(encoding="utf-8")
        settings = load_settings()
        client = create_openai_client(settings)

        try:
            result = analyze_document(
                client,
                model=settings.openai_model,
                document_text=document_text,
            )
        finally:
            client.close()

    except OSError as error:
        print(f"[ERROR] Could not read document: {error}")
        return 1
    except ValueError as error:
        return print_error(error)
    except StructuredAnalysisError as error:
        return print_error(error)
    except openai.APITimeoutError as error:
        return print_error(error)
    except openai.APIConnectionError as error:
        return print_error(error)
    except openai.APIStatusError as error:
        return print_error(error)

    print("[OK] Document analysis received")
    print(f"Document: {args.document}")
    print(f"Model: {settings.openai_model}")
    print(f"Response ID: {result.response_id}")
    print(f"Request ID: {result.request_id or 'unavailable'}")
    print(f"Elapsed Seconds: {result.elapsed_seconds:.3f}")
    print("Analysis:")
    print(f"  Summary: {result.analysis.summary}")
    print("  Key Findings:")

    for finding in result.analysis.key_findings:
        print(f"    - Title: {finding.title}")
        print(f"      Evidence: {finding.evidence}")
        print(f"      Severity: {finding.severity.value}")

    print("  Recommended Actions:")

    if result.analysis.recommended_actions:
        for action in result.analysis.recommended_actions:
            print(f"    - {action}")
    else:
        print("    - none")

    print(
        "  Needs Human Review: "
        f"{str(result.analysis.needs_human_review).lower()}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
