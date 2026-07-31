"""Run the first minimal OpenAI Responses API call."""

from __future__ import annotations

import sys
from pathlib import Path

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_settings
from app.services.openai_client import create_openai_client
from app.services.text_generation import generate_text

FIRST_USER_INPUT = "Agent와 Workflow의 차이를 한 문장으로 설명해 주세요."


def status_error_message(label: str, exc: openai.APIStatusError) -> str:
    request_id = getattr(exc, "request_id", None)
    if request_id:
        return f"{label}. Request ID: {request_id}"
    return label


def main() -> int:
    try:
        settings = load_settings()
        client = create_openai_client(settings)
        try:
            result = generate_text(
                client,
                model=settings.openai_model,
                user_input=FIRST_USER_INPUT,
            )
        finally:
            client.close()
    except ValueError as exc:
        print(f"[ERROR] Invalid input: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"[ERROR] Configuration or response error: {exc}")
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

    print("[OK] OpenAI response received")
    print(f"Model: {settings.openai_model}")
    print(f"Response ID: {result.response_id}")
    print(f"Request ID: {result.request_id or 'unavailable'}")
    if result.usage is None:
        print("Usage: unavailable")
    else:
        print("Usage:")
        print(f"  Input Tokens: {result.usage.input_tokens}")
        print(f"  Cached Input Tokens: {result.usage.cached_input_tokens}")
        print(f"  Output Tokens: {result.usage.output_tokens}")
        print(f"  Reasoning Tokens: {result.usage.reasoning_tokens}")
        print(f"  Total Tokens: {result.usage.total_tokens}")
    print(f"Elapsed Seconds: {result.elapsed_seconds:.3f}")
    print("Answer:")
    print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
