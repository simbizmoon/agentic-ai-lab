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


@dataclass(frozen=True)
class StructuredAnalysisExecution:
    result: StructuredAnalysisResult
    attempts: int
    correction_attempted: bool
    total_usage: TokenUsage | None
    total_elapsed_seconds: float
    response_ids: tuple[str, ...]


def combine_token_usage(
    usages: tuple[TokenUsage | None, ...],
) -> TokenUsage | None:
    present_usages = [usage for usage in usages if usage is not None]
    if not present_usages:
        return None

    return TokenUsage(
        input_tokens=sum(usage.input_tokens for usage in present_usages),
        cached_input_tokens=sum(usage.cached_input_tokens for usage in present_usages),
        output_tokens=sum(usage.output_tokens for usage in present_usages),
        reasoning_tokens=sum(usage.reasoning_tokens for usage in present_usages),
        total_tokens=sum(usage.total_tokens for usage in present_usages),
    )


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
        elapsed_seconds = max(0.0, time.perf_counter() - start_time)
        raise StructuredResponseValidationError(
            "OpenAI structured analysis response failed schema validation",
            elapsed_seconds=elapsed_seconds,
            attempts=1,
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
) -> StructuredAnalysisExecution:
    """Analyze text and retry once only for schema validation failures."""

    try:
        first_result = _analyze_text_once(client, model=model, user_input=user_input)
    except StructuredResponseValidationError as first_error:
        try:
            corrected_result = _analyze_text_once(
                client,
                model=model,
                user_input=user_input,
                correction_instruction=CORRECTION_INSTRUCTION,
            )
        except StructuredResponseValidationError as second_error:
            raise StructuredResponseValidationError(
                "OpenAI structured analysis response failed schema validation after correction",
                elapsed_seconds=(
                    first_error.elapsed_seconds + second_error.elapsed_seconds
                ),
                attempts=2,
            ) from second_error

        return StructuredAnalysisExecution(
            result=corrected_result,
            attempts=2,
            correction_attempted=True,
            total_usage=combine_token_usage((corrected_result.usage,)),
            total_elapsed_seconds=(
                first_error.elapsed_seconds + corrected_result.elapsed_seconds
            ),
            response_ids=(corrected_result.response_id,),
        )

    return StructuredAnalysisExecution(
        result=first_result,
        attempts=1,
        correction_attempted=False,
        total_usage=combine_token_usage((first_result.usage,)),
        total_elapsed_seconds=first_result.elapsed_seconds,
        response_ids=(first_result.response_id,),
    )
