"""Run a minimal OpenAI structured text analysis request."""

from __future__ import annotations

import sys
from pathlib import Path

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_settings
from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
)
from app.services.openai_client import create_openai_client
from app.services.structured_analysis import analyze_text

ANALYSIS_INPUT = (
    "착석 상태를 자동으로 감지하고 장시간 착석 시 "
    "사용자에게 진동 알림을 제공하는 시스템이다."
)


def status_error_message(label: str, exc: openai.APIStatusError) -> str:
    request_id = getattr(exc, "request_id", None)
    if request_id:
        return f"{label}. Request ID: {request_id}"
    return label


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
            result = analyze_text(
                client,
                model=settings.openai_model,
                user_input=ANALYSIS_INPUT,
            )
        finally:
            client.close()
    except ValueError as exc:
        print(f"[ERROR] Invalid input: {exc}")
        return 1
    except StructuredResponseIncompleteError:
        print("[ERROR] Structured analysis response was incomplete")
        return 1
    except StructuredResponseRefusalError:
        print("[ERROR] OpenAI refused the structured analysis request")
        return 1
    except StructuredResponseParseError:
        print("[ERROR] Structured analysis response could not be parsed")
        return 1
    except StructuredResponseStatusError:
        print("[ERROR] Structured analysis response had an unexpected status")
        return 1
    except RuntimeError as exc:
        print(f"[ERROR] Structured analysis error: {exc}")
        return 1
    except openai.AuthenticationError as exc:
        print(status_error_message("[ERROR] OpenAI authentication failed", exc))
        return 1
    except openai.PermissionDeniedError as exc:
        print(status_error_message("[ERROR] OpenAI permission denied", exc))
        return 1
    except openai.BadRequestError as exc:
        print(status_error_message("[ERROR] OpenAI request was invalid", exc))
        return 1
    except openai.NotFoundError as exc:
        print(status_error_message("[ERROR] OpenAI resource was not found", exc))
        return 1
    except openai.RateLimitError as exc:
        print(status_error_message("[ERROR] OpenAI rate limit reached", exc))
        return 1
    except openai.APITimeoutError:
        print("[ERROR] OpenAI request timed out")
        return 1
    except openai.APIConnectionError:
        print("[ERROR] Could not connect to OpenAI API")
        return 1
    except openai.InternalServerError as exc:
        print(status_error_message("[ERROR] OpenAI server error", exc))
        return 1
    except openai.APIStatusError as exc:
        print(status_error_message("[ERROR] OpenAI API returned an error", exc))
        return 1

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
