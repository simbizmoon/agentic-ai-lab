from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import openai
import pytest
from pydantic import ValidationError

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.schemas.text_analysis import Sentiment, TextAnalysis
from app.services.structured_analysis import (
    analyze_text,
    analyze_text_with_correction,
)
from app.services.text_generation import TokenUsage

DEFAULT_OUTPUT = object()


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
    outcomes: list[FakeParsedResponse | BaseException]
    calls: list[dict[str, object]] = field(default_factory=list)
    next_outcome_index: int = 0

    def parse(self, **kwargs: object) -> FakeParsedResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes[self.next_outcome_index]
        self.next_outcome_index += 1

        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class FakeOpenAIClient:
    outcomes: list[FakeParsedResponse | BaseException]

    def __post_init__(self) -> None:
        self.responses = FakeResponses(self.outcomes)


def valid_analysis() -> TextAnalysis:
    return TextAnalysis(
        topic="착석 알림",
        summary="장시간 착석을 감지해 진동으로 알려 주는 시스템이다.",
        sentiment=Sentiment.NEUTRAL,
        keywords=["착석", "진동", "알림"],
        requires_review=False,
        review_reason=None,
    )


def fake_usage() -> FakeUsage:
    return FakeUsage(
        input_tokens=8,
        input_tokens_details=FakeInputTokenDetails(cached_tokens=2),
        output_tokens=12,
        output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=3),
        total_tokens=20,
    )


def make_response(
    *,
    output_parsed: object = DEFAULT_OUTPUT,
    status: str = "completed",
    request_id: str | None = "req_structured",
    usage: FakeUsage | None = None,
    output: list[object] | None = None,
) -> FakeParsedResponse:
    parsed = valid_analysis() if output_parsed is DEFAULT_OUTPUT else output_parsed
    return FakeParsedResponse(
        output_parsed=parsed,
        status=status,
        _request_id=request_id,
        usage=usage,
        output=[] if output is None else output,
    )


def make_client(
    *,
    output_parsed: object = DEFAULT_OUTPUT,
    status: str = "completed",
    request_id: str | None = "req_structured",
    usage: FakeUsage | None = None,
    output: list[object] | None = None,
    outcomes: list[FakeParsedResponse | BaseException] | None = None,
) -> FakeOpenAIClient:
    if outcomes is not None:
        return FakeOpenAIClient(outcomes)

    response = make_response(
        output_parsed=output_parsed,
        status=status,
        request_id=request_id,
        usage=usage,
        output=output,
    )
    return FakeOpenAIClient([response])


def make_validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis.model_validate(
            {
                "topic": "",
                "summary": "요약",
                "sentiment": "neutral",
                "keywords": ["착석"],
                "requires_review": False,
                "review_reason": None,
            }
        )
    return exc_info.value


def make_api_connection_error() -> openai.APIConnectionError:
    request = httpx.Request("POST", "https://example.test/responses")
    return openai.APIConnectionError(message="connection failed", request=request)


def test_analyze_text_returns_text_analysis_object() -> None:
    result = analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert isinstance(result.analysis, TextAnalysis)
    assert result.analysis.topic == "착석 알림"
    assert result.analysis.sentiment is Sentiment.NEUTRAL
    assert result.analysis.review_reason is None


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

    with pytest.raises(StructuredResponseIncompleteError, match="incomplete"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_other_non_completed_status() -> None:
    client = make_client(status="failed")

    with pytest.raises(StructuredResponseStatusError, match="not completed"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_missing_output_parsed() -> None:
    client = make_client(output_parsed=None)

    with pytest.raises(StructuredResponseParseError, match="response was empty"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_output_parsed_with_wrong_type() -> None:
    client = make_client(output_parsed={"topic": "착석"})

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
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

    with pytest.raises(StructuredResponseRefusalError, match="refused"):
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_converts_validation_error_and_calls_once() -> None:
    validation_error = make_validation_error()
    client = make_client(outcomes=[validation_error])

    with pytest.raises(StructuredResponseValidationError, match="schema validation") as exc_info:
        analyze_text(client, model="test-model", user_input="착석 감지 시스템")

    assert len(client.responses.calls) == 1
    assert exc_info.value.__cause__ is validation_error


def test_analyze_text_with_correction_first_success_calls_once() -> None:
    client = make_client()

    result = analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.analysis == valid_analysis()
    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_succeeds_after_validation_error() -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])

    result = analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.analysis == valid_analysis()
    assert len(client.responses.calls) == 2


def test_correction_request_instructions_include_stable_rules() -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])

    analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    second_instructions = client.responses.calls[1]["instructions"]
    assert isinstance(second_instructions, str)
    assert "교정 요청" in second_instructions
    assert "모든 필드" in second_instructions
    assert "추가 필드" in second_instructions
    assert "topic과 summary" in second_instructions
    assert "keywords는 1개 이상 5개 이하" in second_instructions
    assert "대소문자를 무시해 중복" in second_instructions
    assert "review_reason" in second_instructions


def test_correction_request_does_not_include_full_validation_error() -> None:
    validation_error = make_validation_error()
    client = make_client(outcomes=[validation_error, make_response()])

    analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    second_instructions = client.responses.calls[1]["instructions"]
    assert isinstance(second_instructions, str)
    assert str(validation_error) not in second_instructions


def test_analyze_text_with_correction_reraises_second_validation_error() -> None:
    client = make_client(outcomes=[make_validation_error(), make_validation_error()])

    with pytest.raises(StructuredResponseValidationError, match="schema validation"):
        analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 2


def test_analyze_text_with_correction_does_not_retry_refusal() -> None:
    refusal_output = [FakeOutputMessage(content=[FakeRefusalContent("hidden")])]
    client = make_client(output=refusal_output)

    with pytest.raises(StructuredResponseRefusalError, match="refused"):
        analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_incomplete() -> None:
    client = make_client(status="incomplete")

    with pytest.raises(StructuredResponseIncompleteError, match="incomplete"):
        analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_parse_error() -> None:
    client = make_client(output_parsed=None)

    with pytest.raises(StructuredResponseParseError, match="response was empty"):
        analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_api_connection_error() -> None:
    client = make_client(outcomes=[make_api_connection_error()])

    with pytest.raises(openai.APIConnectionError):
        analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1
