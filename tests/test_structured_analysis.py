from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.schemas.text_analysis import Sentiment, TextAnalysis
from app.services.structured_analysis import analyze_text
from app.services.text_generation import TokenUsage


@dataclass(frozen=True)
class FakeInputTokenDetails:
    cached_tokens: int


@dataclass(frozen=True)
class FakeOutputTokenDetails:
    reasoning_tokens: int


@dataclass(frozen=True)
class FakeUsage:
    input_tokens: int
    input_tokens_details: FakeInputTokenDetails
    output_tokens: int
    output_tokens_details: FakeOutputTokenDetails
    total_tokens: int


@dataclass(frozen=True)
class FakeRefusalContent:
    refusal: str


@dataclass(frozen=True)
class FakeOutputMessage:
    content: list[object]


@dataclass(frozen=True)
class FakeParsedResponse:
    output_parsed: object | None
    status: str = "completed"
    id: str = "resp_structured"
    _request_id: str | None = "req_structured"
    usage: FakeUsage | None = None
    output: list[object] = field(default_factory=list)


@dataclass
class FakeResponses:
    response: FakeParsedResponse
    calls: list[dict[str, object]] = field(default_factory=list)

    def parse(self, **kwargs: object) -> FakeParsedResponse:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeOpenAIClient:
    response: FakeParsedResponse

    def __post_init__(self) -> None:
        self.responses = FakeResponses(self.response)


def valid_analysis() -> TextAnalysis:
    return TextAnalysis(
        topic="착석 알림",
        summary="장시간 착석을 감지해 진동으로 알려 주는 시스템이다.",
        sentiment=Sentiment.NEUTRAL,
        keywords=["착석", "진동", "알림"],
        requires_review=False,
    )


def fake_usage() -> FakeUsage:
    return FakeUsage(
        input_tokens=8,
        input_tokens_details=FakeInputTokenDetails(cached_tokens=2),
        output_tokens=12,
        output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=3),
        total_tokens=20,
    )


def make_client(
    *,
    output_parsed: object | None | Any = None,
    status: str = "completed",
    request_id: str | None = "req_structured",
    usage: FakeUsage | None = None,
    output: list[object] | None = None,
) -> FakeOpenAIClient:
    parsed = valid_analysis() if output_parsed is None else output_parsed
    response = FakeParsedResponse(
        output_parsed=parsed,
        status=status,
        _request_id=request_id,
        usage=usage,
        output=[] if output is None else output,
    )
    return FakeOpenAIClient(response)


def test_analyze_text_returns_text_analysis_object() -> None:
    result = analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert isinstance(result.analysis, TextAnalysis)
    assert result.analysis.topic == "착석 알림"
    assert result.analysis.sentiment is Sentiment.NEUTRAL


def test_analyze_text_returns_response_and_request_ids() -> None:
    result = analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.response_id == "resp_structured"
    assert result.request_id == "req_structured"


def test_analyze_text_converts_usage() -> None:
    result = analyze_text(
        make_client(usage=fake_usage()),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.usage == TokenUsage(
        input_tokens=8,
        cached_input_tokens=2,
        output_tokens=12,
        reasoning_tokens=3,
        total_tokens=20,
    )


def test_analyze_text_records_non_negative_elapsed_seconds() -> None:
    result = analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.elapsed_seconds >= 0


def test_analyze_text_calls_parse_once_with_expected_arguments() -> None:
    client = make_client()

    analyze_text(
        client,
        model="test-model",
        user_input="  착석 감지 시스템  ",
    )

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["input"] == "착석 감지 시스템"
    assert call["text_format"] is TextAnalysis
    assert isinstance(call["instructions"], str)
    assert call["instructions"]


def test_analyze_text_rejects_empty_input_without_api_call() -> None:
    client = make_client()

    with pytest.raises(ValueError, match="user_input"):
        analyze_text(client, model="test-model", user_input="   ")

    assert client.responses.calls == []


def test_analyze_text_rejects_incomplete_status() -> None:
    client = make_client(status="incomplete")

    with pytest.raises(RuntimeError, match="incomplete"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_other_non_completed_status() -> None:
    client = make_client(status="failed")

    with pytest.raises(RuntimeError, match="not completed"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_missing_output_parsed() -> None:
    response = FakeParsedResponse(output_parsed=None)
    client = FakeOpenAIClient(response)

    with pytest.raises(RuntimeError, match="response was empty"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_output_parsed_with_wrong_type() -> None:
    client = make_client(output_parsed={"topic": "착석"})

    with pytest.raises(RuntimeError, match="invalid type"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_allows_missing_usage() -> None:
    result = analyze_text(
        make_client(usage=None),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.usage is None


def test_analyze_text_rejects_refusal_response() -> None:
    refusal_output = [FakeOutputMessage(content=[FakeRefusalContent("hidden")])]
    client = make_client(output=refusal_output)

    with pytest.raises(RuntimeError, match="refused"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")
