"""Structured text analysis service using OpenAI Responses API parsing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.schemas.text_analysis import TextAnalysis
from app.services.text_generation import TokenUsage, extract_token_usage

BASE_ANALYSIS_INSTRUCTIONS = (
    "한국어로 주제와 요약을 작성하세요. "
    "sentiment는 positive, neutral, negative 중 하나여야 합니다. "
    "keywords는 1개 이상 5개 이하로 작성하세요. "
    "requires_review에는 추가 검토 필요 여부를 담으세요. "
    "requires_review가 true이면 review_reason에 구체적인 한국어 검토 사유를 작성하세요. "
    "requires_review가 false이면 review_reason은 null이어야 합니다."
)

CORRECTION_INSTRUCTION = (
    "교정 요청: 모든 필드를 정확히 반환하고 추가 필드는 포함하지 마세요. "
    "topic과 summary는 비어 있지 않아야 합니다. "
    "keywords는 1개 이상 5개 이하이며 대소문자를 무시해 중복되면 안 됩니다. "
    "requires_review가 true이면 구체적인 review_reason을 작성하세요. "
    "requires_review가 false이면 review_reason은 null이어야 합니다."
)


@dataclass(frozen=True)
class StructuredAnalysisResult:
    analysis: TextAnalysis
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


def has_refusal(response: Any) -> bool:
    """Return whether a parsed response includes a refusal item."""

    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            if getattr(content_item, "refusal", None):
                return True
    return False


def build_instructions(correction_instruction: str | None) -> str:
    if correction_instruction is None:
        return BASE_ANALYSIS_INSTRUCTIONS
    return f"{BASE_ANALYSIS_INSTRUCTIONS} {correction_instruction}"


def _analyze_text_once(
    client: OpenAI,
    *,
    model: str,
    user_input: str,
    correction_instruction: str | None = None,
) -> StructuredAnalysisResult:
    """Analyze text with exactly one structured output request."""

    cleaned_input = user_input.strip()
    if not cleaned_input:
        raise ValueError("user_input must not be empty")

    start_time = time.perf_counter()
    try:
        response = client.responses.parse(
            model=model,
            instructions=build_instructions(correction_instruction),
            input=cleaned_input,
            text_format=TextAnalysis,
        )
    except ValidationError as error:
        raise StructuredResponseValidationError(
            "OpenAI structured analysis response failed schema validation"
        ) from error
    elapsed_seconds = max(0.0, time.perf_counter() - start_time)

    status = getattr(response, "status", None)
    if status == "incomplete":
        raise StructuredResponseIncompleteError(
            "OpenAI structured analysis response was incomplete"
        )
    if status != "completed":
        raise StructuredResponseStatusError(
            "OpenAI structured analysis response was not completed"
        )

    if has_refusal(response):
        raise StructuredResponseRefusalError(
            "OpenAI refused the structured analysis request."
        )

    analysis = getattr(response, "output_parsed", None)
    if analysis is None:
        raise StructuredResponseParseError(
            "OpenAI structured analysis response was empty"
        )
    if not isinstance(analysis, TextAnalysis):
        raise StructuredResponseParseError(
            "OpenAI structured analysis response has invalid type"
        )

    return StructuredAnalysisResult(
        analysis=analysis,
        response_id=response.id,
        request_id=getattr(response, "_request_id", None),
        usage=extract_token_usage(response),
        elapsed_seconds=elapsed_seconds,
    )


def analyze_text(
    client: OpenAI,
    *,
    model: str,
    user_input: str,
) -> StructuredAnalysisResult:
    """Analyze text without automatic correction."""

    return _analyze_text_once(client, model=model, user_input=user_input)


def analyze_text_with_correction(
    client: OpenAI,
    *,
    model: str,
    user_input: str,
) -> StructuredAnalysisResult:
    """Analyze text and retry once only for schema validation failures."""

    try:
        return _analyze_text_once(client, model=model, user_input=user_input)
    except StructuredResponseValidationError:
        return _analyze_text_once(
            client,
            model=model,
            user_input=user_input,
            correction_instruction=CORRECTION_INSTRUCTION,
        )
