"""Minimal AIRA document analysis using OpenAI Structured Outputs."""

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
from app.schemas.document_analysis import DocumentAnalysis
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

DOCUMENT_ANALYSIS_INSTRUCTIONS = (
    "주어진 문서를 한국어로 분석하세요. "
    "summary에는 문서의 핵심 내용을 작성하세요. "
    "key_findings에는 문서에서 직접 확인할 수 있는 핵심 발견과 근거를 작성하세요. "
    "severity는 low, medium, high 중 하나여야 합니다. "
    "recommended_actions에는 필요한 후속 조치를 작성하세요. "
    "법률, 의료, 재무, 보안 또는 중요한 의사결정이 필요하면 "
    "needs_human_review를 true로 설정하세요. "
    "문서에 없는 내용을 사실처럼 추측하지 마세요."
)


@dataclass(frozen=True)
class DocumentAnalysisResult:
    analysis: DocumentAnalysis
    response_id: str
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


def analyze_document(
    client: OpenAI,
    *,
    model: str,
    document_text: str,
) -> DocumentAnalysisResult:
    """Analyze one document with a validated structured response."""

    cleaned_text = document_text.strip()
    if not cleaned_text:
        raise ValueError("document_text must not be empty")

    start_time = time.perf_counter()

    try:
        response: Any = client.responses.parse(
            model=model,
            instructions=DOCUMENT_ANALYSIS_INSTRUCTIONS,
            input=cleaned_text,
            text_format=DocumentAnalysis,
        )
    except ValidationError as error:
        elapsed_seconds = max(
            0.0,
            time.perf_counter() - start_time,
        )
        raise StructuredResponseValidationError(
            "OpenAI document analysis response failed schema validation",
            elapsed_seconds=elapsed_seconds,
            attempts=1,
        ) from error

    elapsed_seconds = max(
        0.0,
        time.perf_counter() - start_time,
    )

    status = getattr(response, "status", None)

    if status == "incomplete":
        raise StructuredResponseIncompleteError(
            "OpenAI document analysis response was incomplete"
        )

    if status != "completed":
        raise StructuredResponseStatusError(
            "OpenAI document analysis response was not completed"
        )

    if has_refusal(response):
        raise StructuredResponseRefusalError(
            "OpenAI refused the document analysis request"
        )

    analysis = getattr(response, "output_parsed", None)

    if analysis is None:
        raise StructuredResponseParseError(
            "OpenAI document analysis response was empty"
        )

    if not isinstance(analysis, DocumentAnalysis):
        raise StructuredResponseParseError(
            "OpenAI document analysis response has invalid type"
        )

    return DocumentAnalysisResult(
        analysis=analysis,
        response_id=response.id,
        request_id=getattr(response, "_request_id", None),
        usage=extract_token_usage(response),
        elapsed_seconds=elapsed_seconds,
    )
