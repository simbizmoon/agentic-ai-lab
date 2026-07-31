"""Minimal text generation service using the OpenAI Responses API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    from openai.types.responses import Response


@dataclass(frozen=True)
class TokenUsage:
    """Token usage values reported by the Responses API."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class TextGenerationResult:
    """Small, safe result object for generated text."""

    text: str
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


def extract_token_usage(response: Response) -> TokenUsage | None:
    """Extract a small token usage object from an SDK response."""

    usage = response.usage
    if usage is None:
        return None

    return TokenUsage(
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.input_tokens_details.cached_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        total_tokens=usage.total_tokens,
    )


def validate_token_usage(usage: TokenUsage) -> None:
    """Validate token usage consistency."""

    token_values = {
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "total_tokens": usage.total_tokens,
    }
    for name, value in token_values.items():
        if value < 0:
            raise RuntimeError(f"{name} must not be negative")

    if usage.cached_input_tokens > usage.input_tokens:
        raise RuntimeError("cached_input_tokens must not exceed input_tokens")

    if usage.reasoning_tokens > usage.output_tokens:
        raise RuntimeError("reasoning_tokens must not exceed output_tokens")

    if usage.total_tokens != usage.input_tokens + usage.output_tokens:
        raise RuntimeError("total_tokens must equal input_tokens + output_tokens")


def generate_text(
    client: OpenAI,
    *,
    model: str,
    user_input: str,
) -> TextGenerationResult:
    """Generate a short Korean answer for the given user input."""

    cleaned_input = user_input.strip()
    if not cleaned_input:
        raise ValueError("user_input must not be empty")

    start_time = time.perf_counter()
    response = client.responses.create(
        model=model,
        instructions="정확하고 간결한 한국어로 두 문장 이내로 답변하세요.",
        input=cleaned_input,
    )
    elapsed_seconds = max(0.0, time.perf_counter() - start_time)

    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI response text is empty")

    usage = extract_token_usage(response)
    if usage is not None:
        validate_token_usage(usage)

    return TextGenerationResult(
        text=text,
        response_id=response.id,
        request_id=getattr(response, "_request_id", None),
        usage=usage,
        elapsed_seconds=elapsed_seconds,
    )
