"""Structured text analysis service using OpenAI Responses API parsing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
)
from app.schemas.text_analysis import TextAnalysis
from app.services.text_generation import TokenUsage, extract_token_usage


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


def analyze_text(
    client: OpenAI,
    *,
    model: str,
    user_input: str,
) -> StructuredAnalysisResult:
    """Analyze text and return a validated TextAnalysis object."""

    cleaned_input = user_input.strip()
    if not cleaned_input:
        raise ValueError("user_input must not be empty")

    start_time = time.perf_counter()
    response = client.responses.parse(
        model=model,
        instructions=(
            "한국어로 주제와 요약을 작성하세요. "
            "sentiment는 positive, neutral, negative 중 하나여야 합니다. "
            "keywords는 1개 이상 5개 이하로 작성하세요. "
            "requires_review에는 추가 검토 필요 여부를 담으세요. "
            "requires_review가 true이면 review_reason에 구체적인 한국어 검토 사유를 작성하세요. "
            "requires_review가 false이면 review_reason은 null이어야 합니다."
        ),
        input=cleaned_input,
        text_format=TextAnalysis,
    )
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
