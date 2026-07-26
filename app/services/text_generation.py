"""Minimal text generation service using the OpenAI Responses API."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class TextGenerationResult:
    """Small, safe result object for generated text."""

    text: str
    response_id: str
    request_id: str | None


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

    response = client.responses.create(
        model=model,
        instructions="정확하고 간결한 한국어로 두 문장 이내로 답변하세요.",
        input=cleaned_input,
    )

    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI response text is empty")

    return TextGenerationResult(
        text=text,
        response_id=response.id,
        request_id=getattr(response, "_request_id", None),
    )
